import { apiFetch } from "./api";

export function getProjects() {
	return apiFetch("/api/projects");
}

export function createProject(name, description) {
	return apiFetch("/api/projects", {
		method: "POST",
		body: JSON.stringify({ name, description }),
	});
}

export function getProject(projectId) {
	return apiFetch(`/api/projects/${projectId}`);
}

export function searchProjects(query, sort="created_at", direction="desc") {
	const params = new URLSearchParams({ q: query, sort, direction });
	return apiFetch(`/api/search/projects?${params.toString()}`);
}

export function addProjectMember(projectId, userId, role) {
	return apiFetch(`/api/projects/${projectId}/members`, {
		method: "POST",
		body: JSON.stringify({ user_id: userId, role }),
	});
}

export function removeProjectMember(projectId, userId) {
	return apiFetch(`/api/projects/${projectId}/members/${userId}`, {
		method: "DELETE",
	});
}

export function lookupUserByEmail(email) {
	const params = new URLSearchParams({ email });
	return apiFetch(`/api/users/lookup?${params.toString()}`);
}

export function getProjectMessages(projectId) {
	return apiFetch(`/api/projects/${projectId}/messages`);
}

export function sendProjectMessage(projectId, content) {
	return apiFetch(`/api/projects/${projectId}/messages`, {
		method: "POST",
		body: JSON.stringify({ content }),
	});
}

export function deleteProjectMessage(messageId) {
	return apiFetch(`/api/project-messages/${messageId}`, {
		method: "DELETE",
	});
}