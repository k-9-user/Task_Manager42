import { apiFetch } from "./api";

export async function login(email, password) {
	const data = await apiFetch("/api/auth/login", 
		{
			method: "POST",
			body: JSON.stringify({ email, password}),
		}
	);
	localStorage.setItem("token", data.token);
	return data;
}

export async function register(username, email, password) {
	const data = await apiFetch("/api/auth/register", 
		{
			method: "POST",
			body: JSON.stringify({username, email, password}), 
		}
	);
	localStorage.setItem("token", data.token);
	return data;
}

export function logout() {
	localStorage.removeItem("token");
}