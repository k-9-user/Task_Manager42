import { apiFetch } from "./api";

export const googleOAuthUrl = `${import.meta.env.VITE_API_URL}/api/auth/oauth/google`;

export async function login(identifier, password) {
	const data = await apiFetch("/api/auth/login",
		{
			method: "POST",
			body: JSON.stringify({ identifier, password }),
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

export function exchangeGoogleOAuth() {
	return apiFetch("/api/auth/oauth/google/exchange", {
		method: "POST",
		credentials: "same-origin",
	});
}

export function logout() {
	localStorage.removeItem("token");
}
