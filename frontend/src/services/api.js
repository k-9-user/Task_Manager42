const API_URL = import.meta.env.VITE_API_URL;

export async function apiFetch(endpoint, options = {}) {
	const token = localStorage.getItem("token");
	const response = await fetch(`${API_URL}${endpoint}`,
		{ ...options, headers: 
			{
				"Content-Type": "application/json",
				...(token && { Authorization: `Bearer ${token}`}),
				...options.headers,
			},
		}
	);

	const result = await response.json();

	if (!result.success)
		throw new Error(result.error || "Une erreur est survenue");
	return result.data;
}

export async function fetchAuthenticatedBlobUrl(endpoint) {
	const token = localStorage.getItem("token");
	const response = await fetch(`${API_URL}${endpoint}`,
		{
			headers:
			{
				...(token && { Authorization: `Bearer ${token}`}),
			},
		}
	);
	if (!response.ok)
		throw new Error("Une erreur est survenue");
	const blob = await response.blob();
	return URL.createObjectURL(blob);
}