#!/bin/bash

# Function to stop all background processes when the script is terminated
cleanup() {
    echo "Stopping all servers..."
    kill $(jobs -p) 2>/dev/null
    exit
}

# Set up cleanup on script termination
trap cleanup EXIT INT TERM

# Colors for better visibility
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Model selection
echo -e "${YELLOW}Available GPT Models:${NC}"
echo -e "1. GPT-3.5-turbo"
echo -e "   - Input cost: \$0.0015 / 1K tokens"
echo -e "   - Output cost: \$0.002 / 1K tokens"
echo -e "   - Faster, more cost-effective\n"
echo -e "2. GPT-4"
echo -e "   - Input cost: \$0.03 / 1K tokens"
echo -e "   - Output cost: \$0.06 / 1K tokens"
echo -e "   - More capable, better at complex tasks\n"

while true; do
    read -p "Select model (1 or 2): " model_choice
    case $model_choice in
        1)
            MODEL="gpt-3.5-turbo"
            break
            ;;
        2)
            MODEL="gpt-4"
            break
            ;;
        *)
            echo -e "${YELLOW}Please enter 1 or 2${NC}"
            ;;
    esac
done

# Create or update .env file with model choice
echo -e "${BLUE}Setting up environment...${NC}"
if [ ! -f "backend/.env" ]; then
    echo "Creating new .env file..."
    touch backend/.env
fi

# Update or add GPT_MODEL to .env
if grep -q "GPT_MODEL=" "backend/.env"; then
    sed -i '' "s/GPT_MODEL=.*/GPT_MODEL=$MODEL/" backend/.env
else
    echo "GPT_MODEL=$MODEL" >> backend/.env
fi

echo -e "${GREEN}Using model: $MODEL${NC}"

echo -e "${BLUE}Starting backend server...${NC}"
# Start backend server
cd backend
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload &

# Wait a bit for backend to start
sleep 2

echo -e "${GREEN}Starting frontend server...${NC}"
# Start frontend server
cd ../frontend
npm install
npm start &

# Keep the script running
wait 