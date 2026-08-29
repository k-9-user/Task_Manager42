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

const API_URL = import.meta.env.VITE_API_URL;

export async function uploadAttachement(taskID, file)
{
	const token = localStorage.getItem("token");
	const formData = new FormData();

	formData.append("file", file);

	const reponse = await fetch(`${API_URL}/api/tasks/${taskID}/attachements`,
		{
			method: "POST",
			headers:
			{
				...(token && { Authorization: `Bearer ${token}`}),
			},
			body: formData,
		}
	);
	const result = await reponse.json();
	if (!result.success)
		throw new Error(result.error || "Erreur d'upload");
	return result.data;
}

export function deleteAttachment(attachmentId)
{
	return apiFetch(`/api/attachments/${attachmentId} `,
		{
			method: "DELETE"
		}
		);
}