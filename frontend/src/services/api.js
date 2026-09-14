const API_URL = import.meta.env.VITE_API_URL;

export async function apiFetch(endpoint, options = {}) {
	const token = localStorage.getItem("token");
	const response = await fetch(`${API_URL}${endpoint}`,
		{ ...options, headers: 
			{
				"Content-Type": "application/json",
				...(token && { AUthorization: `Bearer ${token}`}),
				...options.headers,
			},
		}
	);

	const result = await response.json();

	if (!result.success)
		throw new Error(result.error || "Une erreur est survenue");
	return result.data;
}