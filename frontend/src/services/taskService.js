import { apiFetch } from "./api";

export function getProjectTasks(projectID) {
	return apiFetch(`/api/projects/${projectID}/tasks`);
}

export function createTask(projectID, title, description) {
	return apiFetch(`/api/projects/${projectID}/tasks`,
		{
			method: "POST",
			body: JSON.stringify({title, description }),
		}
	);
}

export function updateTaskStatus( taskID, status)
{
	return apiFetch(`/api/tasks/${taskID}`,
		{
			method: "PUT",
			body: JSON.stringify({ status }),
			
		}
	);
}

export function searchtask (query, status="")
{
	const params = new URLSearchParams({q : query});
	if (status)
		params.append("status", status);
	return apiFetch(`/api/search/tasks?${params.toString()}`);
}