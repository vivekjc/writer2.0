# Software Engineer's Handbook Generator

This application helps generate a comprehensive Software Engineer's Handbook using OpenAI's GPT model. The application provides a user-friendly interface to:

1. Generate a detailed book outline
2. Review and customize chapter breakdowns
3. Generate chapter content
4. Download the complete book

## Prerequisites

- Node.js (v14 or higher)
- Python (v3.8 or higher)
- OpenAI API key

## Setup

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the backend directory with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

5. Start the backend server:
```bash
uvicorn main:app --reload
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

The application will be available at http://localhost:3000

## Usage

1. **Generate Outline**: Click the "Generate Outline" button to create a detailed chapter-by-chapter outline for the book.

2. **Review Breakdown**: Review the generated outline and customize the word count for each chapter if needed.

3. **Generate Book**: Start the book generation process. Each chapter will be generated sequentially using the OpenAI API.

4. **Download**: Once the generation is complete, you can download the entire book as a text file.

## Project Structure

```
.
├── backend/
│   ├── main.py              # FastAPI backend server
│   └── requirements.txt     # Python dependencies
└── frontend/
    ├── src/
    │   ├── components/      # React components
    │   ├── App.tsx         # Main application component
    │   └── index.tsx       # Application entry point
    └── package.json        # Node.js dependencies
```

## Note

The application uses the OpenAI API, which may incur costs based on your usage. Make sure to monitor your API usage and set appropriate limits. 

## Author

For more projects, visit my GitHub: [Your GitHub Username](https://github.com/vivekjc) 