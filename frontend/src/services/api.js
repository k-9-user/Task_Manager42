const API_URL = import.meta.env.VITE_API_URL;
import { useTranslation } from "react-i18next";

export async function apiFetch(endpoint, options = {}) {
	const token = localStorage.getItem("token");
	const { t } = useTranslation();
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
		throw new Error(result.error || t("random.ersurv"));
	return result.data;
}