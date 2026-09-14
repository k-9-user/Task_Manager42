import { apiFetch } from "./api";
<<<<<<< HEAD
import i18n from "../i18n";
=======
import { useTranslation } from "react-i18next";
>>>>>>> D

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
<<<<<<< HEAD

	formData.append("file", file);

	const reponse = await fetch(`${API_URL}/api/tasks/${taskID}/attachments`,
=======
	const { t } = useTranslation();

	formData.append("file", file);

	const reponse = await fetch(`${API_URL}/api/tasks/${taskID}/attachements`,
>>>>>>> D
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
<<<<<<< HEAD
		throw new Error(result.error || i18n.t("random.upload"));
=======
		throw new Error(result.error || t("random.upload"));
>>>>>>> D
	return result.data;
}

export function deleteAttachment(attachmentId)
{
<<<<<<< HEAD
	return apiFetch(`/api/attachments/${attachmentId}`,
=======
	return apiFetch(`/api/attachments/${attachmentId} `,
>>>>>>> D
		{
			method: "DELETE"
		}
		);
<<<<<<< HEAD
}

export async function uploadTaskBanner(taskID, file)
{
	const token = localStorage.getItem("token");
	const formData = new FormData();

	formData.append("file", file);

	const response = await fetch(`${API_URL}/api/tasks/${taskID}/banner`,
		{
			method: "POST",
			headers:
			{
				...(token && { Authorization: `Bearer ${token}`}),
			},
			body: formData,
		}
	);
	const result = await response.json();
	if (!result.success)
		throw new Error(result.error || i18n.t("random.upload"));
	return result.data;
}

export function deleteTaskBanner(taskID)
{
	return apiFetch(`/api/tasks/${taskID}/banner`,
		{
			method: "DELETE",
		}
	);
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
=======
>>>>>>> D
}