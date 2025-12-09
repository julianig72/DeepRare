# Description: Inference script for running the model on a single input
export PYTHONFAULTHANDLER=1
export CUDA_VISIBLE_DEVICES=0

# ChromeDriver Service Path
SERVICE_PATH="/usr/local/bin/chromedriver"

# google search engine
SEARCH_ID="74f79cca226f84352"
GOOGLE_API="Your_Google_API_Key_Here"

# dataset name
DATASET_NAME="mygene"

# base model
# You can change the model to 'openai', 'deepseek', 'gemini', or 'claude'
# For example, to use OpenAI, set --model openai
# To use DeepSeek, set --model deepseek
# To use Gemini, set --model gemini
# To use Claude, set --model claude
# The default is 'deepseek'
# You can also set the model to 'deepseek-r1-250120' for a specific version of DeepSeek or 'deepseek-v3-241226' for the latest version of DeepSeek
OPENAI_APIKEY="your_openai_api_key"
DEEPSEEK_APIKEY="your_deepseek_api_key"
GEMINI_APIKEY="your_gemini_api_key"
CLAUDE_APIKEY="your_claude_api_key"

python main.py \
    --model openai \
    --dataset_name $DATASET_NAME \
    --search_engine bing \
    --openai_apikey $OPENAI_APIKEY \
    --openai_model gpt-4o \
    --deepseek_apikey $DEEPSEEK_APIKEY \
    --deepseek_model deepseek-v3-241226 \
    --gemini_apikey $GEMINI_APIKEY \
    --gemini_model gemini-2.0-flash \
    --claude_apikey $CLAUDE_APIKEY \
    --claude_model claude-3-7-sonnet-20250219 \
    --chrome_driver $SERVICE_PATH \
    --google_api $GOOGLE_API \
    --search_engine_id $SEARCH_ID \
    --results_folder ./result \

# To run the inference script, use the following command:
# bash inference.sh
