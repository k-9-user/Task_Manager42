import { apiFetch } from "./api";

const API_URL = import.meta.env.VITE_API_URL;

export async function exportMyData()
{
	const token = localStorage.getItem("token");
	const response = await fetch(`${API_URL}/api/gdpr/export`,
		{
			headers:
			{
				...(token && { Authorization: `Bearer ${token}`}),
			},
		}
	);
	if (!response.ok)
		throw new Error("Une erreur est survenue");
	const url = URL.createObjectURL(await response.blob());
	const link = document.createElement("a");
	link.href = url;
	link.download = "gdpr_export.json";
	document.body.appendChild(link);
	link.click();
	link.remove();
	URL.revokeObjectURL(url);
}

export async function deleteMyAccount(username)
{
	return apiFetch("/api/gdpr/account",
		{
			method: "DELETE",
			body: JSON.stringify({ confirm: true, confirm_username: username }),
		}
	);
}

export async function updateMyProfile(fields)
{
	const data = await apiFetch("/api/users/me",
		{
			method: "PUT",
			body: JSON.stringify(fields),
		}
	);
	return data.user;
}
