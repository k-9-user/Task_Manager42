import { apiFetch } from "./api";

export function login(email, password) {
	return apiFetch("/api/auth/login", 
		{
			method: "POST",
			body: JSON.stringify({ email, password}),
		}
	);
}

export function register(username, email, password) {
	return apiFetch("/api/auth/register", 
		{
			method: "POST",
			body: JSON.stringify({username, email, password}), 
		}
	);
}

export function logout() {
	localStorage.removeItem("token");
}