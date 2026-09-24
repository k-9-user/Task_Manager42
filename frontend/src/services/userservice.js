import { apiFetch } from "./api";

export function getUser (filters = {})
{
	const params = new URLSearchParams();
	for (const [key, value] of Object.entries(filters))
		if (value !== undefined && value !== null && value !== "")
			params.set(key, value);
	const query = params.toString();
	return (apiFetch(query ? `/api/users?${query}` : "/api/users"));
}

export function getMe ()
{
	return (apiFetch("/api/users/me"));
}

export function updateuser (iduser, fields)
{
	return (apiFetch(`/api/users/${iduser}`,
		{
			method: "PUT",
			body: JSON.stringify(fields),
		}
	));
}

export function userrole ( iduser, role )
{
	return (apiFetch(`/api/users/${iduser}/role`,
		{
			method: "PUT",
			body: JSON.stringify({ role }),
		}
	));
}

export function deleteuser (iduser)
{
	return (apiFetch(`/api/users/${iduser}`,
		{
			method: "DELETE",
		}
	));
}

export function userstatus (iduser, status)
{
	return (apiFetch(`/api/users/${iduser}/status`,
		{
			method: "PUT",
			body: JSON.stringify({ status }),
		}
	));
}
