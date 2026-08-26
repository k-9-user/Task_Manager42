import { useState, useEffect } from "react";
import { getUser, userrole, userdelete, deleteuser} from "../services/userservice";

function AdminUsers ()
{
	const [Users, setUsers] = useState([]);
	const [ loading, setLoading] = useState(true);
	const [error, setError] = useState("");

	useEffect(() =>
	{
		async function fetchUsers ()
		{
			try
			{
				const data = await getUser();
				setUsers(data.uses);
			}
			catch (err)
			{
				setError(err.message);
			}
			finally
			{
				setLoading(false);
			}
		}
		fetchUsers();
	}, []);

	async function handleRolechange(iduser, newrole)
	{
		setUsers(Users.map((u) => (u.id === iduser ? { ...u, roole: newrole } : u)));

		try
		{
			await userrole (iduser, newrole);
		}
		catch (err)
		{
			setError(err.message);
		}
	}

	async function handledelete(iduser)
	{
		if (!confirm("Supprimer cet utilisateur ?"))
			return ;
		setUsers(Users.filter((u) => u.id !== iduser));

		try
		{
			deleteuser(iduser);
		}
		catch (err)
		{
			setError(err.message);
		}
	}

	if (loading)
		return (<p> Chargement ...</p>);
	if (error)
		return (<p className="error">Erreur : {error} </p>);
	return (
		<div className="admin-user-page">
			<h1>Gestion des utilisateurs</h1>
			<table>
				<thread>
					<tr>
						<th>Nom d'utilisateur</th>
						<th>Email</th>
					</tr>
				</thread>
			</table>
		</div>
	);
}

export default AdminUsers;