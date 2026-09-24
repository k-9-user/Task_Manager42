import i18n from "../i18n";

export const API_URL = import.meta.env.VITE_API_URL;

export const ACTIVITY_EVENT = "taskmanager:activity";

export function notifyActivity() {
	window.dispatchEvent(new Event(ACTIVITY_EVENT));
}

export function authHeaders() {
	const token = localStorage.getItem("token");
	return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiFetch(endpoint, options = {}) {
	const response = await fetch(`${API_URL}${endpoint}`,
		{ ...options, headers: 
			{
				"Content-Type": "application/json",
				...authHeaders(),
				...options.headers,
			},
		}
	);

	const result = await response.json();

	if (!result.success)
		throw new Error(result.error || i18n.t("error.generic"));
	if (options.method && options.method !== "GET")
		notifyActivity();
	return result.data;
}

export async function fetchAuthenticatedBlobUrl(endpoint) {
	const response = await fetch(`${API_URL}${endpoint}`, { headers: authHeaders() });
	if (!response.ok)
		throw new Error(i18n.t("error.generic"));
	const blob = await response.blob();
	return URL.createObjectURL(blob);
}

export async function downloadFile(endpoint, filename) {
	const url = await fetchAuthenticatedBlobUrl(endpoint);
	const link = document.createElement("a");
	link.href = url;
	link.download = filename;
	document.body.appendChild(link);
	link.click();
	link.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}
