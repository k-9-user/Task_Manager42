import { apiFetch } from "./api";

<<<<<<< HEAD
export function login(email, password) {
	return apiFetch("/api/auth/login", 
=======
export async function login(email, password) {
	const data = await apiFetch("/api/auth/login", 
>>>>>>> D
		{
			method: "POST",
			body: JSON.stringify({ email, password}),
		}
	);
<<<<<<< HEAD
}

export function register(username, email, password) {
	return apiFetch("/api/auth/register", 
=======
	localStorage.setItem("token", data.token);
	return data;
}

export async function register(username, email, password) {
	const data = await apiFetch("/api/auth/register", 
>>>>>>> D
		{
			method: "POST",
			body: JSON.stringify({username, email, password}), 
		}
	);
<<<<<<< HEAD
=======
	localStorage.setItem("token", data.token);
	return data;
>>>>>>> D
}

export function logout() {
	localStorage.removeItem("token");
}