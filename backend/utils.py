import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple
import math
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
import openai
from models import Message, ChatResponse

# Directory configuration
DATA_DIR = Path("data")
OUTLINES_DIR = DATA_DIR / "outlines"
BOOKS_DIR = DATA_DIR / "books"
LOGS_DIR = DATA_DIR / "logs"

# Ensure directories exist
OUTLINES_DIR.mkdir(parents=True, exist_ok=True)
BOOKS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

def validate_api_key() -> bool:
    """Validate if OpenAI API key is set in environment variables."""
    return bool(os.getenv("OPENAI_API_KEY"))

def format_messages(messages: List[Message]) -> List[Dict[str, str]]:
    """Convert Message objects to dictionary format required by OpenAI API."""
    return [{"role": msg.role, "content": msg.content} for msg in messages]

def create_chat_response(response: Any) -> ChatResponse:
    """Create ChatResponse object from OpenAI API response."""
    message = response.choices[0].message
    return ChatResponse(role=message.role, content=message.content)

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
    metadata = metadata or {}
    
    if "input_tokens" in metadata and "output_tokens" in metadata:
        try:
            cost = calculate_cost(
                metadata.get("model", os.getenv("GPT_MODEL", "gpt-3.5-turbo")),
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
    
    date = datetime.now().strftime("%Y%m%d")
    log_file = LOGS_DIR / f"gpt_interactions_{date}.json"
    
    if log_file.exists():
        with open(log_file, 'r') as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []
    else:
        logs = []
    
    logs.append(log_entry)
    
    with open(log_file, 'w') as f:
        json.dump(logs, f, indent=2)

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

def get_default_response_limit(model: str = "gpt-3.5-turbo") -> int:
    """Get the default response word limit based on model token limits"""
    WORD_LIMITS = {
        "gpt-3.5-turbo": 1000,
        "gpt-4": 2500,
    }
    return WORD_LIMITS.get(model, WORD_LIMITS["gpt-3.5-turbo"])

def calculate_chunk_size(total_words: int, model: str = "gpt-3.5-turbo") -> Tuple[int, int]:
    """Calculate the optimal chunk size based on model token limits"""
    MODEL_CONFIGS = {
        "gpt-3.5-turbo": {
            "total_tokens": 4000,
            "reserved_tokens": 1000,
            "words_per_token": 0.75,
            "max_words": 750
        },
        "gpt-4": {
            "total_tokens": 8000,
            "reserved_tokens": 2000,
            "words_per_token": 0.75,
            "max_words": 1500
        }
    }
    
    config = MODEL_CONFIGS.get(model, MODEL_CONFIGS["gpt-3.5-turbo"])
    num_chunks = max(1, math.ceil(total_words / config["max_words"]))
    words_per_chunk = math.ceil(total_words / num_chunks / 10) * 10
    
    estimated_tokens = math.ceil(words_per_chunk / config["words_per_token"])
    if estimated_tokens + config["reserved_tokens"] > config["total_tokens"]:
        num_chunks += 1
        words_per_chunk = math.ceil(total_words / num_chunks / 10) * 10
    
    return words_per_chunk, num_chunks

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
    
    story = []
    story.append(Paragraph("Software Engineering Handbook", title_style))
    story.append(Spacer(1, 30))
    
    for chapter in book_data["chapters"]:
        story.append(Paragraph(chapter["title"], chapter_style))
        story.append(Spacer(1, 12))
        
        content_paragraphs = chapter["content"].split('\n\n')
        for para in content_paragraphs:
            if para.strip():
                story.append(Paragraph(para, body_style))
        
        if chapter.get("references"):
            story.append(Spacer(1, 20))
            story.append(Paragraph("References", styles["Heading3"]))
            refs = chapter["references"].split('\n')
            for ref in refs:
                if ref.strip():
                    story.append(Paragraph(ref, reference_style))
        
        story.append(Spacer(1, 30))
    
    doc.build(story)
    return output_path 