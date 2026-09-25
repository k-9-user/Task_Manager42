import { API_URL, TOKEN_KEY, apiFetch } from "./api";

export const googleOAuthUrl = `${API_URL}/api/auth/oauth/google`;

export const googleOAuthEnabled = Boolean(import.meta.env.VITE_GOOGLE_OAUTH);

export async function login(identifier, password) {
	const data = await apiFetch("/api/auth/login",
		{
			method: "POST",
			body: JSON.stringify({ identifier, password }),
		}
	);
	localStorage.setItem(TOKEN_KEY, data.token);
	return data;
}

export async function register(username, email, password) {
	const data = await apiFetch("/api/auth/register", 
		{
			method: "POST",
			body: JSON.stringify({username, email, password}), 
		}
	);
	localStorage.setItem(TOKEN_KEY, data.token);
	return data;
}

export async function exchangeGoogleOAuth() {
	const data = await apiFetch("/api/auth/oauth/google/exchange", {
		method: "POST",
		credentials: "same-origin",
	});
	localStorage.setItem(TOKEN_KEY, data.token);
	return data;
}

export function logout() {
	localStorage.removeItem(TOKEN_KEY);
}

export function isLoggedIn() {
	return !!localStorage.getItem(TOKEN_KEY);
}
