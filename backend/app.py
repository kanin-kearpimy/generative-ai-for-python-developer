from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from openai import AzureOpenAI
from dotenv import load_dotenv
import os
import json

load_dotenv()
app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = MongoClient(os.environ["MONGODB_ATLAS_CLUSTER_URI"])
db_name = "logging"
collection_name = "system-log"
collection = client[db_name][collection_name]

azure_openai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_MODEL_VERSION"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
)
deployment_name = os.getenv("AZURE_OPENAI_MODEL_DEPLOYMENT")

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_recent_log",
            "description": "Call this whenever user ask the general technical question about their system health and logging status. for example, `what is the system today?`. The function should not call when receiving un-related technical questions such as `What's up?`, `Who are you?`",
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_request_log_by_status",
            "description": "Call this whenever user ask the specific technical question about 'status' in their system health  and logging status. for example, `How about good request?`, `How are bad response?`, `What is good request status like?`. The function should not call when receiving un-related technical questions such as `What's up?`, `Who are you?`",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "number",
                        "description": "Status code",
                    },
                },
                "required": ["status"],
            },
        },
    },
]
predefined_prompt_1 = {"role": "system", "content": "You are a helpful assistant."}
predefined_prompt_2 = {
    "role": "system",
    "content": "If you see `request_return_status` is 2xx such as 200, 201, 203, 204. You can assume they are good status. While `request_return_status` is 4xx such as 400, 404, are bad status.",
}


def get_recent_log():
    raw_result = collection.find(
        {},
        {
            "text": 1,
            "request_route": 1,
            "request_return_status": 1,
            "time": 1,
            "_id": 0,
        },
    ).limit(5)
    result = list(raw_result)
    return result


def get_request_log_by_status(status):
    raw_result = collection.find(
        {"request_return_status": status},
        {
            "text": 1,
            "request_route": 1,
            "request_return_status": 1,
            "time": 1,
            "_id": 0,
        },
    )
    result = list(raw_result)
    return result


@app.post("/monitoring-assistant")
async def assistant(request: Request):
    raw_body = await request.json()
    user_message = raw_body["text"]

    response = azure_openai_client.chat.completions.create(
        model=deployment_name,
        messages=[
            predefined_prompt_1,
            {"role": "user", "content": user_message},
        ],
        tools=tools,
        # tool_choice="required",
    )

    result = {
        "message": response.choices[0].message.content,
        "isLog": False,
        "log": None,
    }

    if response.choices[0].message.tool_calls is None:
        return result

    for tool_call in response.choices[0].message.tool_calls:
        if tool_call.function.name == "get_recent_log":
            result["isLog"] = True
            result["log"] = get_recent_log()
            response = azure_openai_client.chat.completions.create(
                model=deployment_name,
                messages=[
                    predefined_prompt_1,
                    predefined_prompt_2,
                    {
                        "role": "system",
                        "content": "Please humanize message when you see JSON of server log. Make it less technical like secretary provide data to one who is not technical person",
                    },
                    {"role": "user", "content": json.dumps(result["log"])},
                ],
            )
            result["message"] = response.choices[0].message.content
        elif tool_call.function.name == "get_request_log_by_status":
            result["isLog"] = True
            argument = json.loads(tool_call.function.arguments)
            result["log"] = get_request_log_by_status(argument["status"])
            response = azure_openai_client.chat.completions.create(
                model=deployment_name,
                messages=[
                    predefined_prompt_1,
                    predefined_prompt_2,
                    {
                        "role": "system",
                        "content": "Please humanize message when you see JSON of server log. Make it less technical like secretary provide data to one who is not technical person",
                    },
                    {"role": "user", "content": json.dumps(result["log"])},
                ],
            )
            result["message"] = response.choices[0].message.content
        else:
            response = azure_openai_client.chat.completions.create(
                model=deployment_name,
                messages=[
                    predefined_prompt_1,
                ],
            )
            result["message"] = response.choices[0].message.content

    return result
