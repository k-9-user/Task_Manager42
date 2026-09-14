import { apiFetch } from "./api";

export function getUser ()
{
	return (apiFetch("./api/users"));
}

export function userrole ( iduser, role )
{
	return (apiFetch(`./api/users/${iduser}/role`,
		{
			method: "PUT",
			body: JSON.stringify({ role }),
		}
	));
}

export function deleteuser (iduser)
{
	return (apiFetch(`.api/users/${iduser}`,
		{
			method: "DELETE",
		}
	));
}