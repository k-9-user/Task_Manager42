import { apiFetch, downloadFile } from "./api";

export function exportMyData()
{
	return downloadFile("/api/gdpr/export", "gdpr_export.json");
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
