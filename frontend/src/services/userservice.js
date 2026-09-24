import { apiFetch } from "./api";

export function getUsers (filters = {})
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

export async function updateMe (fields)
{
	const data = await apiFetch("/api/users/me",
		{
			method: "PUT",
			body: JSON.stringify(fields),
		}
	);
	return (data.user);
}

export function updateUser (userId, fields)
{
	return (apiFetch(`/api/users/${userId}`,
		{
			method: "PUT",
			body: JSON.stringify(fields),
		}
	));
}

export function setUserRole (userId, role)
{
	return (apiFetch(`/api/users/${userId}/role`,
		{
			method: "PUT",
			body: JSON.stringify({ role }),
		}
	));
}

export function deleteUser (userId)
{
	return (apiFetch(`/api/users/${userId}`,
		{
			method: "DELETE",
		}
	));
}

export function setUserStatus (userId, status)
{
	return (apiFetch(`/api/users/${userId}/status`,
		{
			method: "PUT",
			body: JSON.stringify({ status }),
		}
	));
}
