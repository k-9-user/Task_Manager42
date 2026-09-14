const API_URL = import.meta.env.VITE_API_URL;
<<<<<<< HEAD
import i18n from "../i18n";
=======
>>>>>>> D

export async function apiFetch(endpoint, options = {}) {
	const token = localStorage.getItem("token");
	const response = await fetch(`${API_URL}${endpoint}`,
<<<<<<< HEAD
		{ ...options, headers:
			{
				"Content-Type": "application/json",
				...(token && { Authorization: `Bearer ${token}`}),
=======
		{ ...options, headers: 
			{
				"Content-Type": "application/json",
				...(token && { AUthorization: `Bearer ${token}`}),
>>>>>>> D
				...options.headers,
			},
		}
	);

	const result = await response.json();

	if (!result.success)
<<<<<<< HEAD
		throw new Error(result.error || i18n.t("random.ersurv"));
=======
		throw new Error(result.error || "Une erreur est survenue");
>>>>>>> D
	return result.data;
}