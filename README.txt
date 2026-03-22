									- PROJECT OVERVIEW - 

	I want this project to culminate in a web plugin that can do certain monotonous tasks that otherwise would fall into my purview as an analyst. 

	What this truly means is, it should be able to take in a prompt and perform:
	- Create tickets (Features, Stories, Tasks, Sub-tasks, Bugs, and Spikes)
	- Create multiple of these tickets, in a row, with one command/prompt.
	- Add: Descriptions, Assignees, Priority level, Blockers, and Due Dates.
	- Respond to the prompt with a link to the tickets created.

									    - EXAMPLE - 

	"I need you to create 4 stories under the INF070 Feature. These tickets should be as follows:
	Ticket 1:
		Title: Development work
		Description: Development work for INF070
		Assignee: Tehna Lopez
		Priority: Ready for Sprint
	Ticket 2:
		Title: Create Confluence Page for INF 070
		Description: 'Confluence page link:'
		Assignee: Mary
		Priority: In Progress
	Ticket 3:
		Title: Testing for INF070
		Description: Handled by John
		Assignee: John 
		Priority: Not Ready
		Blocked by: 'Development work'"
		"


									- PROJECT OUTLINE - 
	Needs:
	 - A frontend
	 - A backend (Might need to use Python + JQL in order to make this work)
	 - Permissions from Jira (Have my own project for this)

	 								   - FRONTEND - 
	To get this ready, I will need:
	 - HTML
	 - CSS
	 - Manifest V3
	 - React?

	 								   - BACKEND - 

	For the backend, I will use:
	 - Python
	 - Manifest V3
	 - Flask API
	 - OpenAI API
	 - JIRA API

Here's the flow:
User enters in natural language prompt ("I want yada yada made")
OpenAI API takes the prompt and condenses it into the important information like Title, description, etc
This information gets assigned to variables like the example from Jira api's docs below:

		payload = json.dumps( 
			{
			"assigneeType": "PROJECT_LEAD",
			"categoryId": 10120,
			"description": "Cloud migration initiative",
			"key": "EX",
			"leadAccountId": "5b10a0effa615349cb016cd8",
			"name": "Example",
			"projectTemplateKey": "com.atlassian.jira-core-project-templates:jira-core-simplified-process-control",
			"projectTypeKey": "business",
			"url": "http://atlassian.com"
			} )

Have all starting from the { sign be the response, assign this to a variable, lets just say "dump", then do:
	payload = json.dumps(dump)... 
Otherwise, have it be returned as some sort of list or dictionary and use a for loop to assign each variable to its corresponding
value.

From here we need the JIRA API to connect to the environment (should prob go at the top of the code), and use the values in the
given payload to create the tickets.




