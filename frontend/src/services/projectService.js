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