#!/bin/bash

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    set -a  # automatically export all variables
    source .env
    set +a
fi

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo "Error: AWS SAM CLI is not installed."
    echo "Please install it using one of these methods:"
    echo ""
    echo "1. Using Homebrew (macOS):"
    echo "   brew install aws-sam-cli"
    echo ""
    echo "2. Using pip:"
    echo "   pip install aws-sam-cli"
    echo ""
    echo "3. Download from AWS:"
    echo "   Visit: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html"
    exit 1
fi

# Configuration
STACK_NAME="flight-search-bot"
STAGE=${1:-dev}  # Use first argument as stage, default to dev
FORCE=${2:-false}  # Use second argument as force flag, default to false
REGION=${AWS_DEFAULT_REGION:-"us-east-1"}  # Use AWS_DEFAULT_REGION or default to "us-east-1"
S3_BUCKET="flight-search-bot-deployment-${STAGE}"
CONFIG_BUCKET="flight-search-bot-config-${STAGE}"

# Function to check if a bucket exists
check_bucket_exists() {
    local bucket=$1
    aws s3api head-bucket --bucket "$bucket" 2>/dev/null
    return $?
}

# Function to empty and delete a bucket
delete_bucket() {
    local bucket=$1
    echo "Emptying bucket: $bucket"
    aws s3 rm "s3://${bucket}" --recursive
    echo "Deleting bucket: $bucket"
    aws s3api delete-bucket --bucket "$bucket"
}

# Function to check stack status
check_stack_status() {
    local stack_name=$1
    local status
    status=$(aws cloudformation describe-stacks --stack-name "$stack_name" --query 'Stacks[0].StackStatus' --output text 2>/dev/null)
    echo "$status"
}

# Function to delete stack
delete_stack() {
    local stack_name=$1
    echo "Deleting stack: $stack_name"
    aws cloudformation delete-stack --stack-name "$stack_name"
    echo "Waiting for stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name "$stack_name"
}

# Function to clean build directory
clean_build_dir() {
    local build_dir=".aws-sam"
    if [ -d "$build_dir" ]; then
        echo "Cleaning build directory..."
        rm -rf "$build_dir"
    fi
}

# Check for AWS credentials
echo "Checking for AWS credentials..."
MISSING_AWS_VARS=()
if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    MISSING_AWS_VARS+=("AWS_ACCESS_KEY_ID")
fi
if [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    MISSING_AWS_VARS+=("AWS_SECRET_ACCESS_KEY")
fi

# If any AWS variables are missing, show error and exit
if [ ${#MISSING_AWS_VARS[@]} -gt 0 ]; then
    echo "Error: Missing required AWS credentials:"
    for VAR in "${MISSING_AWS_VARS[@]}"; do
        echo "  - $VAR"
    done
    echo "Please set these variables in your .env file or environment."
    echo "Example .env file contents:"
    echo "  AWS_ACCESS_KEY_ID=your_access_key"
    echo "  AWS_SECRET_ACCESS_KEY=your_secret_key"
    echo "  AWS_DEFAULT_REGION=us-east-1"
    exit 1
fi

# Check for required environment variables
echo "Checking for required environment variables..."
MISSING_VARS=()
# Check required variables
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    MISSING_VARS+=("TELEGRAM_BOT_TOKEN")
fi

if [ -z "$TELEGRAM_CHAT_ID" ]; then
    MISSING_VARS+=("TELEGRAM_CHAT_ID")
fi

if [ -z "$AMADEUS_CLIENT_ID" ]; then
    MISSING_VARS+=("AMADEUS_CLIENT_ID")
fi

if [ -z "$AMADEUS_CLIENT_SECRET" ]; then
    MISSING_VARS+=("AMADEUS_CLIENT_SECRET")
fi

# If any variables are missing, show error and exit
if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo "Error: Missing required environment variables:"
    for VAR in "${MISSING_VARS[@]}"; do
        echo "  - $VAR"
    done
    echo "Please set these variables in your .env file."
    exit 1
fi

# Check if stack exists and handle force flag
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" &>/dev/null; then
    if [ "$FORCE" = "true" ]; then
        echo "Force flag is set. Deleting existing stack..."
        delete_stack "$STACK_NAME"
    else
        echo "Stack $STACK_NAME already exists. Use force flag to delete and recreate:"
        echo "  ./deploy.sh $STAGE true"
        exit 1
    fi
fi

# Create deployment bucket if it doesn't exist
if ! check_bucket_exists "$S3_BUCKET"; then
    echo "Creating deployment bucket: $S3_BUCKET"
    if [ "$REGION" = "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "$S3_BUCKET" \
            --region "$REGION" || {
            echo "Failed to create deployment bucket"
            exit 1
        }
    else
        aws s3api create-bucket \
            --bucket "$S3_BUCKET" \
            --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION" || {
            echo "Failed to create deployment bucket"
            exit 1
        }
    fi
fi

# Create config bucket if it doesn't exist
if ! check_bucket_exists "$CONFIG_BUCKET"; then
    echo "Creating config bucket: $CONFIG_BUCKET"
    if [ "$REGION" = "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "$CONFIG_BUCKET" \
            --region "$REGION" || {
            echo "Failed to create config bucket"
            exit 1
        }
    else
        aws s3api create-bucket \
            --bucket "$CONFIG_BUCKET" \
            --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION" || {
            echo "Failed to create config bucket"
            exit 1
        }
    fi
fi

# Upload config.json to config bucket
echo "Uploading config.json to config bucket..."
aws s3 cp config.json "s3://${CONFIG_BUCKET}/config.json" || {
    echo "Failed to upload config.json"
    exit 1
}

# Clean build directory before building
clean_build_dir

# Build the application
echo "Building the application..."
sam build || {
    echo "Failed to build the application"
    exit 1
}

# Deploy the application
echo "Deploying the application..."
if ! sam deploy \
    --stack-name "$STACK_NAME" \
    --s3-bucket "$S3_BUCKET" \
    --region "$REGION" \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        Stage="$STAGE" \
        ConfigBucketName="$CONFIG_BUCKET" \
        TelegramBotToken="$TELEGRAM_BOT_TOKEN" \
        TelegramChatId="$TELEGRAM_CHAT_ID" \
        AmadeusClientId="$AMADEUS_CLIENT_ID" \
        AmadeusClientSecret="$AMADEUS_CLIENT_SECRET" \
    --no-fail-on-empty-changeset; then
    echo "Error: Deployment failed!"
    echo "Checking stack status..."
    STACK_STATUS=$(check_stack_status "$STACK_NAME")
    echo "Stack status: $STACK_STATUS"
    
    if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ]; then
        echo "Stack is in ROLLBACK_COMPLETE state. This means the deployment failed and was rolled back."
        echo "To fix this, try running the script with the force flag to delete and recreate the stack:"
        echo "  ./deploy.sh $STAGE true"
    fi
    exit 1
fi

# Get the API Gateway URL
API_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`TelegramWebhookUrl`].OutputValue' \
    --output text)

if [ "$API_URL" = "None" ]; then
    echo "Error: Failed to get API Gateway URL. The deployment may have failed."
    exit 1
fi

echo "================================================================"
echo "Deployment successful!"
echo "Telegram Webhook URL: $API_URL"
echo ""
echo "Set up your Telegram webhook using:"
echo "curl -X POST \"https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${API_URL}\""
echo "================================================================" 