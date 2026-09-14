import { apiFetch } from "./api";

<<<<<<< HEAD
export function getCurrentUser ()
{
	return (apiFetch("/api/users/me"));
}

export function getUser ()
{
	return (apiFetch("/api/users"));
=======
export function getUser ()
{
	return (apiFetch("./api/users"));
>>>>>>> D
}

export function userrole ( iduser, role )
{
<<<<<<< HEAD
	return (apiFetch(`/api/users/${iduser}/role`,
=======
	return (apiFetch(`./api/users/${iduser}/role`,
>>>>>>> D
		{
			method: "PUT",
			body: JSON.stringify({ role }),
		}
	));
}

export function deleteuser (iduser)
{
<<<<<<< HEAD
	return (apiFetch(`/api/users/${iduser}`,
=======
	return (apiFetch(`.api/users/${iduser}`,
>>>>>>> D
		{
			method: "DELETE",
		}
	));
}