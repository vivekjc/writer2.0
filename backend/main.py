from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import openai
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from models import (
    ChatRequest, ChatResponse, OutlineRequest, 
    ChapterContent, ResponseBreakdownRequest
)
from utils import (
    validate_api_key, format_messages, create_chat_response,
    log_gpt_interaction, save_outline, save_book,
    calculate_chunk_size, generate_pdf,
    BOOKS_DIR, LOGS_DIR
)
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

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

@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    if not validate_api_key():
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        response = await openai.ChatCompletion.acreate(
            model=request.model,
            messages=format_messages(request.messages),
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        return create_chat_response(response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 