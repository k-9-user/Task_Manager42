import { apiFetch } from "./api";

export function getProjects() {
	return apiFetch("/api/projects");
}

export function getProject(projectId) {
	return apiFetch(`/api/projects/${projectId}`);
}

export function lookupUserByEmail(email) {
	return apiFetch(`/api/users/lookup?email=${encodeURIComponent(email)}`);
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

export function createProject(name, description) {
	return apiFetch("/api/projects", {
		method: "POST",
		body: JSON.stringify({ name, description }),
	});
}