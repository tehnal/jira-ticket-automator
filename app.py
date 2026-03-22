from openai import OpenAI
from dotenv import load_dotenv
import os
from jira import JIRA
import json

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
jira_token = os.getenv("JIRA_API_TOKEN")
jira_server = os.getenv("JIRA_SERVER")
jira_email = os.getenv("JIRA_EMAIL")

# Initialize JIRA client
jira = JIRA(
    server=jira_server,
    basic_auth=(jira_email, jira_token)
)

# Initialize OpenAI client
client = OpenAI()


def ticket_create(prompt):
    prompt = f"""
    Extract the following fields from this input for a JIRA ticket:
    - summary
    - description
    - assignee (if mentioned)
    - parent (if mentioned)
    - work_type (if mentioned, could be things like "Development", "Bug Fix", "Testing", "Research", etc.)
    - components (if mentioned, could be specific system components or modules)
    - priority (if mentioned, like "High", "Medium", "Low")

    Respond ONLY with valid JSON in this format:
    {{
        "summary": "...",
        "description": "...",
        "assignee": "...",     // or null if not mentioned
        "parent": "...",       // or null if not mentioned
        "work_type": "...",    // or null if not mentioned
        "components": ["..."], // array of components or null if not mentioned
        "priority": "..."      // or null if not mentioned
    }}

    Input: "{prompt}"
    """

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.1,
    )

    return completion.choices[0].message.content


def get_available_issue_types(jira, project_key):
    """Get all available issue types for a project"""
    try:
        project = jira.project(project_key)
        issue_types = jira.issue_types()
        
        print(f"Available issue types for project {project_key}:")
        for issue_type in issue_types:
            print(f"  - {issue_type.name} (ID: {issue_type.id})")
            
        return issue_types
    except Exception as e:
        print(f"Error getting issue types: {e}")
        return []


def find_subtask_issue_type(jira, project_key):
    """Find a valid sub-task issue type"""
    issue_types = get_available_issue_types(jira, project_key)
    
    # Common sub-task type names to try
    subtask_names = ['Sub-task', 'Subtask', 'sub-task', 'subtask', 'Bug', 'Story']
    
    for issue_type in issue_types:
        if issue_type.subtask:  # Check if it's actually a sub-task type
            print(f"Found sub-task type: {issue_type.name}")
            return issue_type.name
            
    # If no sub-task types found, try common names
    for subtask_name in subtask_names:
        for issue_type in issue_types:
            if issue_type.name == subtask_name:
                print(f"Using issue type: {issue_type.name}")
                return issue_type.name
                
    print("No suitable sub-task issue type found")
    return None


def get_custom_fields(jira):
    """Get all custom fields and their IDs"""
    try:
        fields = jira.fields()
        custom_fields = {}
        
        print("Available custom fields:")
        for field in fields:
            if field['custom']:
                custom_fields[field['name']] = field['id']
                print(f"  - {field['name']}: {field['id']}")
        
        return custom_fields
    except Exception as e:
        print(f"Error getting custom fields: {e}")
        return {}


def get_components(jira, project_key):
    """Get available components for the project"""
    try:
        project = jira.project(project_key)
        components = jira.project_components(project)
        
        print(f"Available components for {project_key}:")
        comp_dict = {}
        for comp in components:
            comp_dict[comp.name] = comp.id
            print(f"  - {comp.name} (ID: {comp.id})")
        
        return comp_dict
    except Exception as e:
        print(f"Error getting components: {e}")
        return {}


def create_ticket(jira, summary, description, assignee=None, parent=None, work_type=None, components=None, priority=None):
    # Get custom fields and components info
    custom_fields = get_custom_fields(jira)
    available_components = get_components(jira, 'KAN')
    
    # Base issue structure
    issue_dict = {
        'project': {'key': 'KAN'},
        'summary': summary,
        'description': description,
    }
    
    # Set issue type based on whether it has a parent
    if parent:
        subtask_type = find_subtask_issue_type(jira, 'KAN')
        if not subtask_type:
            print("❌ Could not find valid sub-task issue type. Creating as regular task without parent.")
            issue_dict['issuetype'] = {'name': 'Task'}
            parent = None  # Remove parent since we can't create sub-task
        else:
            issue_dict['issuetype'] = {'name': subtask_type}
            issue_dict['parent'] = {'key': parent}
    else:
        issue_dict['issuetype'] = {'name': 'Task'}
    
    # Add assignee if provided
    if assignee:
        issue_dict['assignee'] = {'accountId': assignee}
    
    # Add priority if provided
    if priority:
        issue_dict['priority'] = {'name': priority}
    
    # Add components if provided
    if components and available_components:
        component_list = []
        for comp_name in components:
            # Try exact match first, then partial match
            matched_comp = None
            for available_comp in available_components:
                if comp_name.lower() == available_comp.lower():
                    matched_comp = available_comp
                    break
            
            if not matched_comp:
                # Try partial match
                for available_comp in available_components:
                    if comp_name.lower() in available_comp.lower():
                        matched_comp = available_comp
                        break
            
            if matched_comp:
                component_list.append({'id': available_components[matched_comp]})
                print(f"Matched component: {comp_name} -> {matched_comp}")
            else:
                print(f"Could not match component: {comp_name}")
        
        if component_list:
            issue_dict['components'] = component_list
    
    # Add work type (this is likely a custom field)
    if work_type and custom_fields:
        # Look for common work type field names
        work_type_field_names = ['Work Type', 'WorkType', 'Type of Work', 'Work Category']
        work_type_field_id = None
        
        for field_name in work_type_field_names:
            if field_name in custom_fields:
                work_type_field_id = custom_fields[field_name]
                break
        
        if work_type_field_id:
            # Work type might be a select field, try different formats
            try:
                issue_dict[work_type_field_id] = {'value': work_type}
                print(f"Set work type: {work_type}")
            except:
                # If select format doesn't work, try as string
                issue_dict[work_type_field_id] = work_type
                print(f"Set work type (string): {work_type}")
        else:
            print(f"Could not find Work Type custom field")
    
    print(f"Creating issue with structure: {json.dumps(issue_dict, indent=2)}")
    
    try:
        new_issue = jira.create_issue(fields=issue_dict)
        print(f"Successfully created issue: {new_issue.key}")
        
        if assignee:
            print(f"Issue assigned to account ID: {assignee}")
        
        if parent:
            print(f"Issue created as sub-task of: {parent}")
        
        if components:
            print(f"Components set: {components}")
            
        if work_type:
            print(f"Work type set: {work_type}")
            
        return new_issue
        
    except Exception as e:
        print(f"Failed to create issue: {e}")
        print(f"Issue structure that failed: {json.dumps(issue_dict, indent=2)}")
        
        # If it fails, try without custom fields
        print("Retrying without custom fields...")
        minimal_issue_dict = {
            'project': {'key': 'KAN'},
            'summary': summary,
            'description': description,
            'issuetype': issue_dict['issuetype']
        }
        
        if assignee:
            minimal_issue_dict['assignee'] = {'accountId': assignee}
        if parent:
            minimal_issue_dict['parent'] = {'key': parent}
        if priority:
            minimal_issue_dict['priority'] = {'name': priority}
            
        try:
            new_issue = jira.create_issue(fields=minimal_issue_dict)
            print(f"Successfully created minimal issue: {new_issue.key}")
            return new_issue
        except Exception as e2:
            print(f"Failed to create even minimal issue: {e2}")
            raise


def clean_openai_response(response):
    # Remove triple backticks and optional "json" label
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
                
        print(f"No match found for assignee name: {name}")
        return None
        
    except Exception as e:
        print(f"Error searching for user '{name}': {e}")
        return None


def validate_parent_ticket(jira, parent_key):
    """Validate that the parent ticket exists and can have sub-tasks"""
    if not parent_key:
        return True
        
    try:
        parent_issue = jira.issue(parent_key)
        print(f"Parent ticket {parent_key} found: {parent_issue.fields.summary}")
        return True
    except Exception as e:
        print(f"Error validating parent ticket {parent_key}: {e}")
        return False


############################################################################################################################################

user_input = "Create a ticket for 'Accounts recievable are bad'. Description is '2024-01-19 Q1 accounts recievable aren't balanced'. Assign to Tehna Lopez, have it under the parent ticket KAN-2, set work type to 'AWS', components should be 'Development Workstream', priority High"

# Get ticket data from OpenAI
print("Getting ticket data from OpenAI...")
ticket_data = ticket_create(user_input)
final_response = clean_openai_response(ticket_data)

# Convert AI response to JSON
try:
    ticket_data = json.loads(final_response)
    print("Parsed ticket data:")
    print(json.dumps(ticket_data, indent=2))
except json.JSONDecodeError:
    print("OpenAI response was not valid JSON:")
    print(final_response)
    ticket_data = {}
    exit(1)

# Get assignee account ID
assignee_name = ticket_data.get("assignee")
account_id = None
if assignee_name:
    print(f"Looking up assignee: {assignee_name}")
    account_id = get_account_id(jira, assignee_name)
    if account_id:
        print(f"Found account ID: {account_id}")
    else:
        print(f"Could not find account ID for: {assignee_name}")

# Validate parent ticket
parent_key = ticket_data.get("parent")
if parent_key and not validate_parent_ticket(jira, parent_key):
    print(f"Parent ticket validation failed. Creating without parent.")
    parent_key = None

# Create ticket
print("\n Creating JIRA ticket...")
try:
    issue = create_ticket(
        jira,
        summary=ticket_data.get('summary', 'No summary provided'),
        description=ticket_data.get('description', 'No description provided'),
        assignee=account_id,
        parent=parent_key,
        work_type=ticket_data.get('work_type'),
        components=ticket_data.get('components'),
        priority=ticket_data.get('priority')
    )
    
    print(f"\nSuccess!")
    print(f"Ticket created: {issue.key}")
    print(f"View it at: {jira_server}/browse/{issue.key}")
    
except Exception as e:
    print(f"Failed to create ticket: {e}")