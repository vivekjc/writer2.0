from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import openai
import os
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
import math

# Load environment variables
load_dotenv()

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

GPT_MODEL = os.getenv("GPT_MODEL", "gpt-3.5-turbo")  # Default to GPT-3.5 if not specified

# Configure data directories
DATA_DIR = Path("data")
OUTLINES_DIR = DATA_DIR / "outlines"
BOOKS_DIR = DATA_DIR / "books"
LOGS_DIR = DATA_DIR / "logs"

# Ensure directories exist
OUTLINES_DIR.mkdir(parents=True, exist_ok=True)
BOOKS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate the cost of an API call based on the model and token usage"""
    costs = {
        "gpt-3.5-turbo": {
            "input": 0.0015,   # $0.0015 per 1K input tokens
            "output": 0.002    # $0.002 per 1K output tokens
        },
        "gpt-4": {
            "input": 0.03,     # $0.03 per 1K input tokens
            "output": 0.06     # $0.06 per 1K output tokens
        }
    }
    
    if model not in costs:
        raise ValueError(f"Unknown model: {model}")
        
    model_costs = costs[model]
    input_cost = (input_tokens / 1000) * model_costs["input"]
    output_cost = (output_tokens / 1000) * model_costs["output"]
    
    return input_cost + output_cost

def log_gpt_interaction(interaction_type: str, prompt: str, response: str, metadata: dict = None):
    """Log GPT interaction to a JSON file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Ensure metadata exists
    metadata = metadata or {}
    
    # Add token counts and cost if available
    if "input_tokens" in metadata and "output_tokens" in metadata:
        try:
            cost = calculate_cost(
                metadata.get("model", GPT_MODEL),
                metadata["input_tokens"],
                metadata["output_tokens"]
            )
            metadata["cost_usd"] = round(cost, 6)
            metadata["total_tokens"] = metadata["input_tokens"] + metadata["output_tokens"]
        except Exception as e:
            print(f"Error calculating cost: {str(e)}")
    
    log_entry = {
        "timestamp": timestamp,
        "type": interaction_type,
        "prompt": prompt,
        "response": response,
        "metadata": metadata
    }
    
    # Create a daily log file
    date = datetime.now().strftime("%Y%m%d")
    log_file = LOGS_DIR / f"gpt_interactions_{date}.json"
    
    # Read existing logs or create new list
    if log_file.exists():
        with open(log_file, 'r') as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []
    else:
        logs = []
    
    # Append new log entry
    logs.append(log_entry)
    
    # Write updated logs
    with open(log_file, 'w') as f:
        json.dump(logs, f, indent=2)

class OutlineRequest(BaseModel):
    prompt: str
    pageCount: int

class OutlineResponse(BaseModel):
    chapters: List[dict]

class ChapterContent(BaseModel):
    chapter_id: int
    content: str

class ResponseBreakdownRequest(BaseModel):
    chapter_title: str
    content: str
    sections: List[str]
    total_word_count: int
    response_word_limit: Optional[int] = None  # Make this optional

def get_default_response_limit(model: str = "gpt-3.5-turbo") -> int:
    """Get the default response word limit based on model token limits"""
    # Model specific word limits (based on token limits, leaving room for prompt)
    WORD_LIMITS = {
        "gpt-3.5-turbo": 1000,  # ~3K tokens for response, 1K for prompt
        "gpt-4": 2500,          # ~6K tokens for response, 2K for prompt
    }
    return WORD_LIMITS.get(model, WORD_LIMITS["gpt-3.5-turbo"])

def save_outline(outline: str, page_count: int) -> str:
    """Save the outline to a file and return the filename"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"outline_{timestamp}.json"
    
    data = {
        "timestamp": timestamp,
        "page_count": page_count,
        "outline": outline
    }
    
    filepath = OUTLINES_DIR / filename
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    return filename

def save_book(chapters: List[dict], outline_filename: str) -> str:
    """Save the generated book to a file and return the filename"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"book_{timestamp}.json"
    
    data = {
        "timestamp": timestamp,
        "outline_file": outline_filename,
        "chapters": chapters
    }
    
    filepath = BOOKS_DIR / filename
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Also save a text version for easy reading
    text_filepath = BOOKS_DIR / f"book_{timestamp}.txt"
    with open(text_filepath, 'w') as f:
        for chapter in chapters:
            f.write(f"{chapter['title']}\n\n")
            f.write(f"{chapter['content']}\n\n")
            if chapter.get('references'):
                f.write("References:\n")
                f.write(chapter['references'] + "\n\n")
            f.write("=" * 80 + "\n\n")
    
    return filename

@app.post("/api/generate-outline")
async def generate_outline(request: OutlineRequest):
    print("\n=== Starting generate_outline ===")
    try:
        print("Step 1: Checking OpenAI API key...")
        if not openai.api_key:
            print("Error: OpenAI API key not found")
            raise HTTPException(status_code=500, detail="OpenAI API key is not set. Please check your .env file.")
        print(f"API key found: {openai.api_key[:5]}...")

        print("Step 2: Calculating word counts...")
        min_words = request.pageCount * 800
        max_words = request.pageCount * 1000
        print(f"Page count: {request.pageCount}, Min words: {min_words}, Max words: {max_words}")
        
        print("Step 3: Preparing system prompt...")
        system_prompt = f"""You are a professional book outline generator. Create a detailed chapter-by-chapter outline for a software engineering book.
        The total word count should be between {min_words} and {max_words} words.
        
        IMPORTANT: For each chapter, you MUST include the word count in exactly this format: (Word Count: N) where N is the number of words.
        The word count should appear immediately after the chapter title.
        
        For each chapter, provide:
        1. Chapter title with word count in parentheses
        2. Brief description
        3. Key sections/topics
        4. Suggested key references and papers to be cited (2-3 per chapter)
        
        Format each chapter exactly like this:
        Chapter X: Title (Word Count: N)
        Brief description of the chapter.
        Sections:
        - Section 1
        - Section 2
        etc.
        Key References:
        - Reference 1 (with brief explanation of relevance)
        - Reference 2 (with brief explanation of relevance)

        Make sure the total of all chapter word counts falls within the specified range of {min_words} to {max_words} words.
        Allocate word counts based on the complexity and importance of each topic.
        """

        print("Step 4: Preparing messages...")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.prompt}
        ]

        print(f"Step 5: Making OpenAI API call using model: {GPT_MODEL}")
        print(f"User prompt: {request.prompt}")
        
        try:
            print("Calling OpenAI API...")
            response = openai.ChatCompletion.create(
                model=GPT_MODEL,
                messages=messages,
                temperature=0.7
            )
            print("OpenAI API call successful")
        except openai.AuthenticationError as auth_error:
            print(f"OpenAI Authentication Error: {str(auth_error)}")
            raise HTTPException(status_code=500, detail="OpenAI API key is invalid or expired")
        except openai.RateLimitError as rate_error:
            print(f"OpenAI Rate Limit Error: {str(rate_error)}")
            raise HTTPException(status_code=429, detail="OpenAI API rate limit exceeded. Please try again later.")
        except openai.APIError as api_error:
            print(f"OpenAI API Error: {str(api_error)}")
            raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(api_error)}")
        except Exception as api_error:
            print(f"Unexpected OpenAI API error: {str(api_error)}")
            raise HTTPException(status_code=500, detail=f"Unexpected error calling OpenAI API: {str(api_error)}")
        
        print("Step 6: Processing API response...")
        outline = response.choices[0].message.content
        print("Step 7: Saving outline...")
        outline_filename = save_outline(outline, request.pageCount)

        print("Step 8: Logging interaction...")
        log_gpt_interaction(
            "outline_generation",
            json.dumps(messages),
            outline,
            {
                "page_count": request.pageCount,
                "outline_filename": outline_filename,
                "model": GPT_MODEL
            }
        )
        
        print("Step 9: Returning response...")
        return {
            "outline": outline,
            "filename": outline_filename
        }
    except HTTPException as he:
        print(f"HTTP Exception in generate_outline: {str(he)}")
        print(f"HTTP Exception details: {he.detail}")
        raise he
    except Exception as e:
        print(f"Unexpected error in generate_outline: {str(e)}")
        print("Full error details:")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        print("=== Ending generate_outline ===\n")

@app.post("/api/generate-chapter")
async def generate_chapter(chapter: ChapterContent):
    try:
        system_prompt = """You are writing a comprehensive software engineering book chapter.
        Each chapter should be well-researched and include proper citations and references.
        
        IMPORTANT RULES:
        1. You MUST write the EXACT number of words specified in the request
        2. Use in-text citations throughout the chapter using [1], [2], etc.
        3. Include a "References" section at the end in IEEE style
        4. Include both classic foundational works and recent developments
        5. Include DOI or URL where applicable
        6. Do not skip or shorten the content to meet word count
        7. Ensure comprehensive coverage of all topics
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chapter.content}
        ]
        
        print(f"Using model: {GPT_MODEL}")
        response = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=messages,
            temperature=0.7
        )

        chapter_content = response.choices[0].message.content

        # Log the interaction with token usage
        log_gpt_interaction(
            "chapter_generation",
            json.dumps(messages),
            chapter_content,
            {
                "chapter_id": chapter.chapter_id,
                "model": GPT_MODEL,
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        )
        
        return {"content": chapter_content}
    except Exception as e:
        print(f"Error generating chapter: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/save-book")
async def save_completed_book(data: dict):
    try:
        filename = save_book(data["chapters"], data["outline_filename"])
        return {"filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/list-books")
async def list_books():
    try:
        books = []
        for file in BOOKS_DIR.glob("*.json"):
            with open(file, 'r') as f:
                book_data = json.load(f)
                books.append({
                    "filename": file.name,
                    "timestamp": book_data["timestamp"],
                    "outline_file": book_data["outline_file"]
                })
        return {"books": sorted(books, key=lambda x: x["timestamp"], reverse=True)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/list-logs")
async def list_logs():
    """List all available GPT interaction logs"""
    try:
        logs = []
        for file in LOGS_DIR.glob("*.json"):
            with open(file, 'r') as f:
                log_data = json.load(f)
                logs.append({
                    "filename": file.name,
                    "date": file.stem.split('_')[-1],
                    "interaction_count": len(log_data)
                })
        return {"logs": sorted(logs, key=lambda x: x["date"], reverse=True)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/get-log/{date}")
async def get_log(date: str):
    """Get all GPT interactions for a specific date"""
    try:
        log_file = LOGS_DIR / f"gpt_interactions_{date}.json"
        if not log_file.exists():
            raise HTTPException(status_code=404, detail="Log file not found")
            
        with open(log_file, 'r') as f:
            logs = json.load(f)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def calculate_chunk_size(total_words: int, model: str = "gpt-3.5-turbo") -> tuple[int, int]:
    """Calculate the optimal chunk size based on model token limits
    Returns (words_per_chunk, num_chunks)"""
    
    # Model specific configurations
    MODEL_CONFIGS = {
        "gpt-3.5-turbo": {
            "total_tokens": 4000,    # Total token limit
            "reserved_tokens": 1000,  # Reserved for prompt, overhead
            "words_per_token": 0.75,  # Approximate words per token
            "max_words": 750         # (4000-1000) * 0.75 ≈ 750 words safe limit
        },
        "gpt-4": {
            "total_tokens": 8000,
            "reserved_tokens": 2000,
            "words_per_token": 0.75,
            "max_words": 1500        # (8000-2000) * 0.75 ≈ 1500 words safe limit
        }
    }
    
    config = MODEL_CONFIGS.get(model, MODEL_CONFIGS["gpt-3.5-turbo"])
    
    # Calculate number of chunks needed based on safe word limit
    num_chunks = max(1, math.ceil(total_words / config["max_words"]))
    
    # Distribute words evenly across chunks, rounded up to nearest 10
    words_per_chunk = math.ceil(total_words / num_chunks / 10) * 10
    
    # Verify we're within token limits
    estimated_tokens = math.ceil(words_per_chunk / config["words_per_token"])
    if estimated_tokens + config["reserved_tokens"] > config["total_tokens"]:
        # If we exceed token limit, recalculate with one more chunk
        num_chunks += 1
        words_per_chunk = math.ceil(total_words / num_chunks / 10) * 10
    
    print(f"Chunk calculation for {model}:")
    print(f"Total words: {total_words}")
    print(f"Number of chunks: {num_chunks}")
    print(f"Words per chunk: {words_per_chunk}")
    print(f"Estimated tokens per chunk: {estimated_tokens}")
    
    return words_per_chunk, num_chunks

@app.post("/api/break-into-responses")
async def break_into_responses(request: ResponseBreakdownRequest):
    try:
        print(f"Received breakdown request for chapter: {request.chapter_title}")
        
        if request.total_word_count <= 0:
            raise HTTPException(status_code=400, detail="Total word count must be greater than 0")
        
        if not request.chapter_title or not request.content:
            raise HTTPException(status_code=400, detail="Chapter title and content are required")

        # Calculate optimal chunk size based on model limits
        words_per_chunk, num_chunks = calculate_chunk_size(
            request.total_word_count,
            GPT_MODEL
        )
        
        print(f"Using model: {GPT_MODEL}")
        print(f"Total words: {request.total_word_count}")
        print(f"Calculated {num_chunks} responses needed, {words_per_chunk} words per response")
        
        system_prompt = f"""You are helping to break down a book chapter into smaller, manageable response chunks.
        Your task is to create {num_chunks} responses, each with approximately {words_per_chunk} words.
        
        IMPORTANT FORMATTING RULES:
        1. You MUST create EXACTLY {num_chunks} responses
        2. Each response MUST be separated by exactly five equals signs and the response number
        3. Each response MUST follow the exact format provided
        4. Each response MUST contain enough points to generate {words_per_chunk} words
        5. Points should be detailed enough to generate comprehensive content
        6. Each point should require 200-300 words to explain properly
        7. Content MUST flow logically between chunks
        """

        prompt = f"""Break down the following chapter into EXACTLY {num_chunks} separate responses.

Chapter: {request.chapter_title}
Description: {request.content}

Sections to cover:
{chr(10).join(f"- {section}" for section in request.sections)}

STRICT REQUIREMENTS:
1. Create EXACTLY {num_chunks} responses (no more, no less)
2. Each response MUST be exactly {words_per_chunk} words when generated
3. Total word count MUST be exactly {request.total_word_count} words
4. Content must flow logically between responses
5. Each response must cover a distinct part of the content
6. Include enough points to generate {words_per_chunk} words per response
7. Make points detailed enough to require 200-300 words each
8. First response MUST include introduction
9. Last response MUST include conclusion and references

Format EACH response EXACTLY like this:

===== Response 1 =====
Title: [Clear and specific title for this section]
Word Count: {words_per_chunk}
Points to Cover:
- [Detailed point that requires 200-300 words to explain]
- [Another detailed point with multiple aspects to cover]
- [Complex point that needs examples and detailed explanation]
=====

[Continue this exact format for all {num_chunks} responses]"""

        print("Sending request to GPT...")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        response = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=messages,
            temperature=0.3,  # Lower temperature for more structured output
            presence_penalty=0.0,
            frequency_penalty=0.0
        )

        print("Received response from GPT, parsing...")
        content = response.choices[0].message.content
        print(f"Raw GPT response: {content[:200]}...") # Print first 200 chars for debugging

        # Parse the response into structured format
        raw_responses = [resp.strip() for resp in content.split('===== Response') if resp.strip()]
        parsed_responses = []
        
        print(f"Found {len(raw_responses)} response sections")
        
        for i, raw_response in enumerate(raw_responses, 1):
            try:
                print(f"\nProcessing response section {i}:")
                print(f"Raw text: {raw_response[:200]}...")
                
                # Split into lines and clean up
                lines = [line.strip() for line in raw_response.split('\n') if line.strip()]
                print(f"Found {len(lines)} lines")
                
                # Extract title
                title = None
                for line in lines:
                    if line.startswith('Title:'):
                        title = line.replace('Title:', '').strip()
                        break
                
                if not title:
                    print(f"Warning: No title found in response {i}, lines: {lines[:3]}")
                    continue
                print(f"Found title: {title}")
                
                # Extract word count
                word_count = None
                for line in lines:
                    if 'Word Count:' in line:
                        try:
                            word_count = int(''.join(filter(str.isdigit, line)))
                            break
                        except ValueError:
                            print(f"Warning: Could not parse word count from line: {line}")
                            continue
                
                if word_count is None:
                    print(f"Warning: No word count found in response {i}")
                    continue
                print(f"Found word count: {word_count}")
                
                # Extract points
                points = []
                points_section_started = False
                for line in lines:
                    if 'Points to Cover:' in line:
                        points_section_started = True
                        continue
                    if points_section_started and line.startswith('-'):
                        point = line.replace('-', '', 1).strip()
                        if point:
                            points.append(point)
                
                if not points:
                    print(f"Warning: No valid points found in response {i}")
                    continue
                
                print(f"Found {len(points)} points: {points[:2]}...")
                
                parsed_responses.append({
                    "title": title,
                    "wordCount": word_count,
                    "points": points
                })
                print(f"Successfully parsed response {i}")
                
            except Exception as e:
                print(f"Error parsing response {i}: {str(e)}")
                print("Full response text:")
                print(raw_response)
                continue

        if not parsed_responses:
            print("No responses were successfully parsed")
            print("Full GPT response:")
            print(content)
            raise HTTPException(
                status_code=500,
                detail="Failed to parse any valid responses from GPT output"
            )

        # Verify we got the correct number of responses
        if len(parsed_responses) != num_chunks:
            print(f"Warning: Expected {num_chunks} responses but got {len(parsed_responses)}")
            raise HTTPException(
                status_code=500,
                detail=f"Expected {num_chunks} responses but got {len(parsed_responses)}"
            )

        # Log the interaction with token usage
        log_gpt_interaction(
            "response_breakdown",
            json.dumps(messages),
            content,
            {
                "chapter_title": request.chapter_title,
                "total_word_count": request.total_word_count,
                "num_chunks": num_chunks,
                "words_per_chunk": words_per_chunk,
                "model": GPT_MODEL,
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens
            }
        )

        print(f"Successfully parsed {len(parsed_responses)} responses")
        return {"responses": parsed_responses}
        
    except HTTPException as he:
        print(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

def generate_pdf(book_data: dict, output_path: Path) -> Path:
    """Generate a PDF version of the book"""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Create styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    chapter_style = ParagraphStyle(
        'ChapterTitle',
        parent=styles['Heading2'],
        fontSize=18,
        spaceAfter=20
    )
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=12,
        leading=14,
        spaceAfter=12
    )
    reference_style = ParagraphStyle(
        'Reference',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=20,
        spaceAfter=6
    )
    
    # Build the document
    story = []
    
    # Add title
    story.append(Paragraph("Software Engineering Handbook", title_style))
    story.append(Spacer(1, 30))
    
    # Add chapters
    for chapter in book_data["chapters"]:
        # Chapter title
        story.append(Paragraph(chapter["title"], chapter_style))
        story.append(Spacer(1, 12))
        
        # Chapter content
        content_paragraphs = chapter["content"].split('\n\n')
        for para in content_paragraphs:
            if para.strip():
                story.append(Paragraph(para, body_style))
        
        # References section if present
        if chapter.get("references"):
            story.append(Spacer(1, 20))
            story.append(Paragraph("References", styles["Heading3"]))
            refs = chapter["references"].split('\n')
            for ref in refs:
                if ref.strip():
                    story.append(Paragraph(ref, reference_style))
        
        story.append(Spacer(1, 30))
    
    # Build the PDF
    doc.build(story)
    return output_path

@app.get("/api/download-book/{filename}")
async def download_book(filename: str, format: str = "pdf"):
    """Download a book in the specified format"""
    try:
        # Get the book data
        book_path = BOOKS_DIR / filename
        if not book_path.exists():
            raise HTTPException(status_code=404, detail="Book not found")
        
        with open(book_path, 'r') as f:
            book_data = json.load(f)
        
        if format.lower() == "pdf":
            # Generate PDF filename
            pdf_filename = f"book_{book_data['timestamp']}.pdf"
            pdf_path = BOOKS_DIR / pdf_filename
            
            # Generate PDF if it doesn't exist
            if not pdf_path.exists():
                generate_pdf(book_data, pdf_path)
            
            return FileResponse(
                path=pdf_path,
                filename=pdf_filename,
                media_type="application/pdf"
            )
        else:
            # Return the text version
            text_filename = f"book_{book_data['timestamp']}.txt"
            text_path = BOOKS_DIR / text_filename
            
            if not text_path.exists():
                raise HTTPException(status_code=404, detail="Text version not found")
            
            return FileResponse(
                path=text_path,
                filename=text_filename,
                media_type="text/plain"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cost-summary/{date}")
async def get_cost_summary(date: str):
    """Get a summary of API costs for a specific date"""
    try:
        log_file = LOGS_DIR / f"gpt_interactions_{date}.json"
        if not log_file.exists():
            raise HTTPException(status_code=404, detail="Log file not found")
            
        with open(log_file, 'r') as f:
            logs = json.load(f)
        
        # Calculate totals
        total_cost = 0.0
        total_tokens = 0
        model_usage = {}
        interaction_types = {}
        
        for entry in logs:
            metadata = entry.get("metadata", {})
            cost = metadata.get("cost_usd", 0)
            tokens = metadata.get("total_tokens", 0)
            model = metadata.get("model", "unknown")
            interaction_type = entry.get("type", "unknown")
            
            total_cost += cost
            total_tokens += tokens
            
            # Track model usage
            if model not in model_usage:
                model_usage[model] = {
                    "cost": 0.0,
                    "tokens": 0,
                    "calls": 0
                }
            model_usage[model]["cost"] += cost
            model_usage[model]["tokens"] += tokens
            model_usage[model]["calls"] += 1
            
            # Track interaction types
            if interaction_type not in interaction_types:
                interaction_types[interaction_type] = {
                    "cost": 0.0,
                    "tokens": 0,
                    "calls": 0
                }
            interaction_types[interaction_type]["cost"] += cost
            interaction_types[interaction_type]["tokens"] += tokens
            interaction_types[interaction_type]["calls"] += 1
        
        return {
            "date": date,
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
            "total_calls": len(logs),
            "model_usage": model_usage,
            "interaction_types": interaction_types
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 