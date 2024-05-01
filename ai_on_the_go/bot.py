from fastapi import FastAPI, Request, Response, HTTPException
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import logging
import os
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain_groq import ChatGroq
from collections import defaultdict

# initialize FastAPI
app = FastAPI()

# Get all the API keys:
GROQ_API_KEY = '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'
BOT_TOKEN = '7144711700:AAE3Wt-vrcpfM43wSK1eMFUMFXPcYKfte64'

# Heroku App name
HEROKU_APP_NAME = 'ai-on-the-go'

# Telegram bot setup
bot = Bot(token=BOT_TOKEN)
application = Application.builder().token(BOT_TOKEN).build()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Groq client
#groq_client = AsyncGroq(api_key=GROQ_API_KEY)
# Setup the client
llm = ChatGroq(temperature=0.8, groq_api_key=GROQ_API_KEY, model_name='llama3-70b-8192')

# Dictionary to manage conversation for each user
conversations = defaultdict(lambda: None)

@app.on_event("startup")
async def startup():
    # Initialize the application
    await application.initialize()

    webhook_url = f"https://ai-on-the-go-7a6698c2fd9b.herokuapp.com/webhook"
    await bot.set_webhook(url=webhook_url)
    logger.info("Webhook setup complete at %s", webhook_url)

# Command handler for /start
async def start(update:Update, context):
    logger.debug("Received /start command from user %s", update.effective_chat.id)
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Hello! Welcome to AI On The Go Bot! Send any message to start AI-On The Go Bot."
        )
    except Exception as e:
        logger.error("Failed to send start message due to: %s", str(e))
        raise e


# setup the conversation in Langchain
async def setup_llm_converation(llm):
    """
    Sets the conversation class from langchain.
    :param llm: llm class from langchain
    :return: conversation class from langchain
    """
    conversation = ConversationChain(
        llm=llm,
        memory=ConversationBufferMemory(),
        verbose=False
    )
    return conversation
async def get_llm_response(conversation, user_input):
    """
    Gets response from user input from langchain llm.
    :param user_input: user message extracted from telegram
    :return: returns a response from llm
    """
    response = await conversation.ainvoke(user_input)
    return response['response']

# Get message from user -> send to Groq API -> send back the response
async def handle_message(update:Update, context):
    user_text = update.message.text # extract text from the user message
    user_id = update.effective_chat.id
    logger.debug("Received message from user %s: %s", update.effective_chat.id, user_text)

    # check if user has a conversation
    if conversations[user_id] is None:
        conversations[user_id] = await setup_llm_converation(llm)


    try:
        chat_response = await get_llm_response(conversations[user_id], user_text)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=chat_response)
        logger.debug("Sent response to user %s: %s", update.effective_chat.id, chat_response)
    except Exception as e:
        logger.error("Error during message handling: %s", str(e))
        raise e


# Add handlers to the application
application.add_handler(CommandHandler('start', start))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

# Setup the webhook
@app.post('/webhook')
async def webhook(request: Request):
    data = await request.json()
    logger.debug(f"Received webhook data: {data}")
    update = Update.de_json(data, bot)
    await application.process_update(update)
    return Response(status_code=200)


# Run the app using Uvicorn, if the script is run directly
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)