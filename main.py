from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import json
from openai import OpenAI
from dotenv import load_dotenv
import os
from jira import JIRA

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI(
    title="JIRA AI Assistant", 
    description="Your JIRA bot converted to a web API",
    version="1.0.0"
)

# Enable CORS so web browsers can talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=api_key)

# Simple storage for demo (replace with database later)
users_db = {}      # Stores logged-in users
jira_configs = {}  # Stores JIRA configurations per user


def ticket_create(prompt):
    prompt_template = f"""
    Extract the following fields from this input for a JIRA ticket:
    - summary
    - description
    - assignee (if mentioned)
    - parent (if mentioned)
    - work_type (if mentioned)
    - components (if mentioned, as array)
    - priority (if mentioned)

    Respond ONLY with valid JSON in this format:
    {{
        "summary": "...",
        "description": "...",
        "assignee": "...",  // or null if not mentioned
        "parent": "...",    // or null if not mentioned  
        "work_type": "...", // or null if not mentioned
        "components": ["..."], // array of components or null
        "priority": "..."   // or null if not mentioned
    }}

    Input: "{prompt}"
    """

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt_template}],
        max_tokens=300,
        temperature=0.1,
    )

    return completion.choices[0].message.content

def clean_openai_response(response):
    if response.startswith("```"):
        response = response.strip("`").strip()
        if response.startswith("json"):
            response = response[4:].strip()
    return response

def get_account_id(jira, name):
    if not name:
        return None
        
    try:
        users = jira.search_users(query=name)
        print(f"Found {len(users)} users matching '{name}'")
        
        for user in users:
            print(f"User: {user.displayName} (ID: {user.accountId})")
            if user.displayName.lower() == name.lower():
                return user.accountId
                
        # If no exact match, try partial match
        for user in users:
            if name.lower() in user.displayName.lower():
                print(f"Using partial match: {user.displayName}")
                return user.accountId
                
        print(f" No match found for assignee name: {name}")
        return None
        
    except Exception as e:
        print(f" Error searching for user '{name}': {e}")
        return None

def validate_parent_ticket(jira, parent_key):
    if not parent_key:
        return True
        
    try:
        parent_issue = jira.issue(parent_key)
        print(f" Parent ticket {parent_key} found: {parent_issue.fields.summary}")
        return True
    except Exception as e:
        print(f" Error validating parent ticket {parent_key}: {e}")
        return False

def find_subtask_issue_type(jira, project_key):
    try:
        issue_types = jira.issue_types()
        
        # Look for sub-task types first
        for issue_type in issue_types:
            if hasattr(issue_type, 'subtask') and issue_type.subtask:
                print(f" Found sub-task type: {issue_type.name}")
                return issue_type.name
                
        # If no sub-task types found, try common names
        subtask_names = ['Sub-task', 'Subtask', 'sub-task', 'subtask']
        for subtask_name in subtask_names:
            for issue_type in issue_types:
                if issue_type.name == subtask_name:
                    print(f" Using issue type: {issue_type.name}")
                    return issue_type.name
                    
        print(" No suitable sub-task issue type found")
        return None
        
    except Exception as e:
        print(f" Error getting issue types: {e}")
        return None

def create_ticket(jira, summary, description, assignee=None, parent=None, work_type=None, components=None, priority=None, project_key='KAN'):
    issue_dict = {
        'project': {'key': project_key},
        'summary': summary,
        'description': description,
    }
    
    # Set issue type based on whether it has a parent
    if parent:
        subtask_type = find_subtask_issue_type(jira, project_key)
        if not subtask_type:
            print(" Could not find valid sub-task issue type. Creating as regular task without parent.")
            issue_dict['issuetype'] = {'name': 'Task'}
            parent = None
        else:
            issue_dict['issuetype'] = {'name': subtask_type}
            issue_dict['parent'] = {'key': parent}
    else:
        issue_dict['issuetype'] = {'name': 'Task'}
    
    # Add optional fields
    if assignee:
        issue_dict['assignee'] = {'accountId': assignee}
    
    if priority:
        issue_dict['priority'] = {'name': priority}
    
    print(f"Creating issue with structure: {json.dumps(issue_dict, indent=2)}")
    
    try:
        new_issue = jira.create_issue(fields=issue_dict)
        print(f" Successfully created issue: {new_issue.key}")
        return new_issue
        
    except Exception as e:
        print(f" Failed to create issue: {e}")
        raise


# These define the JSON structure for web requests

class LoginRequest(BaseModel):
    email: str
    password: str

class JiraConfig(BaseModel):
    user_id: str
    jira_server: str
    jira_email: str  
    jira_token: str

class TicketRequest(BaseModel):
    user_id: str
    user_input: str  # Natural language description

# Web API Endpoints

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": " Your JIRA AI Assistant is running!", 
        "status": "healthy",
        "version": "1.0.0"
    }

@app.post("/auth/login")
async def login(request: LoginRequest):
    """Simple login for the web interface"""
    # Generate user ID from email
    user_id = str(abs(hash(request.email)))
    
    user_data = {
        "id": user_id,
        "email": request.email,
        "name": request.email.split('@')[0]
    }
    
    # Store user
    users_db[user_id] = user_data
    
    return {"success": True, "user": user_data}

@app.post("/jira/configure")
async def configure_jira(config: JiraConfig):
    """Test and save JIRA configuration"""
    try:
        # Test connection using your existing JIRA setup logic
        jira = JIRA(
            server=config.jira_server,
            basic_auth=(config.jira_email, config.jira_token)
        )
        
        # Test connection
        current_user = jira.current_user()
        
        # Save configuration if test passes
        jira_configs[config.user_id] = {
            "jira_server": config.jira_server,
            "jira_email": config.jira_email,
            "jira_token": config.jira_token
        }
        
        return {
            "success": True, 
            "message": f" JIRA connected successfully as {current_user}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JIRA connection failed: {str(e)}")

@app.post("/ticket/create")
async def create_ticket_api(request: TicketRequest):
    """
    Main endpoint - does exactly what your script does:
    1. Parse natural language with OpenAI
    2. Create JIRA ticket
    """
    try:
        # Check JIRA configuration
        if request.user_id not in jira_configs:
            raise HTTPException(status_code=400, detail="Please configure JIRA first")
        
        config = jira_configs[request.user_id]
        
        # Initialize JIRA client
        jira = JIRA(
            server=config["jira_server"],
            basic_auth=(config["jira_email"], config["jira_token"])
        )
        
        print("🤖 Processing ticket request...")
        print(f"Input: {request.user_input}")
        
        # Step 1: Parse with OpenAI (your existing logic)
        ticket_data_raw = ticket_create(request.user_input)
        cleaned_response = clean_openai_response(ticket_data_raw)
        
        try:
            ticket_data = json.loads(cleaned_response)
            print(f"📋 Parsed data: {json.dumps(ticket_data, indent=2)}")
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Failed to parse AI response")
        
        # Step 2: Resolve assignee (your existing logic)
        assignee_name = ticket_data.get("assignee")
        account_id = None
        if assignee_name:
            account_id = get_account_id(jira, assignee_name)
            if account_id:
                print(f" Found assignee: {assignee_name} -> {account_id}")
        
        # Step 3: Validate parent ticket (your existing logic)
        parent_key = ticket_data.get("parent")
        if parent_key and not validate_parent_ticket(jira, parent_key):
            parent_key = None
        
        # Step 4: Create ticket (your existing logic)
        issue = create_ticket(
            jira,
            summary=ticket_data.get('summary', 'No summary provided'),
            description=ticket_data.get('description', 'No description provided'),
            assignee=account_id,
            parent=parent_key,
            priority=ticket_data.get('priority'),
            project_key='KAN'  # Make this configurable later
        )
        
        # Return success response
        ticket_url = f"{config['jira_server']}/browse/{issue.key}"
        
        return {
            "success": True,
            "ticket": {
                "key": issue.key,
                "url": ticket_url,
                "summary": ticket_data.get('summary'),
                "description": ticket_data.get('description'),
                "assignee": assignee_name,
                "parent": parent_key,
                "priority": ticket_data.get('priority')
            },
            "message": f" Ticket {issue.key} created successfully!"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f" Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard/{user_id}")
async def get_dashboard(user_id: str):
    """Dashboard stats - you can enhance this later"""
    return {
        "success": True,
        "stats": {
            "tickets_created_today": 0,
            "total_tickets": 0,
            "active_projects": 1,
            "time_saved_hours": 0
        }
    }

# ============================================================================
# SECTION 6: SERVER STARTUP
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    print("Starting JIRA AI Assistant API...")
    print("Interactive docs: http://localhost:8000/docs")
    print("Health check: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
