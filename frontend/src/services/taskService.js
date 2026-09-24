import { apiFetch } from "./api";
import { uploadWithProgress } from "./upload";

export const TASK_STATUSES = ["todo", "in_progress", "done"];

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

export function updateTaskDescription(taskID, description)
{
	return apiFetch(`/api/tasks/${taskID}`,
		{
			method: "PUT",
			body: JSON.stringify({ description }),
		}
	);
}

export function deleteTask(taskID)
{
	return apiFetch(`/api/tasks/${taskID}`,
		{
			method: "DELETE",
		}
	);
}

export function searchTasks (query, status="", sort="created_at", direction="desc")
{
	const params = new URLSearchParams({q : query, sort, direction});
	if (status)
		params.append("status", status);
	return apiFetch(`/api/search/tasks?${params.toString()}`);
}


export function uploadAttachment(taskID, file, onProgress)
{
	return uploadWithProgress(`/api/tasks/${taskID}/attachments`, file, onProgress);
}

export function getTaskAttachments(taskID)
{
	return apiFetch(`/api/tasks/${taskID}/attachments`);
}

export function deleteAttachment(attachmentId)
{
	return apiFetch(`/api/attachments/${attachmentId}`,
		{
			method: "DELETE"
		}
		);
}

export function uploadTaskBanner(taskID, file, onProgress)
{
	return uploadWithProgress(`/api/tasks/${taskID}/banner`, file, onProgress);
}

export function getTaskComments(taskID)
{
	return apiFetch(`/api/tasks/${taskID}/comments`);
}

export function addComment(taskID, content)
{
	return apiFetch(`/api/tasks/${taskID}/comments`,
		{
			method: "POST",
			body: JSON.stringify({ content }),
		}
	);
}

export function deleteComment(commentId)
{
	return apiFetch(`/api/comments/${commentId}`,
		{
			method: "DELETE",
		}
	);
}
