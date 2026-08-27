import { useState, useEffect } from "react";
import { getUser, userrole, deleteuser} from "../services/userservice.js";

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
						<th>Role</th>
						<th>Action</th>
					</tr>
				</thread>
				<tbody>
					{Users.map((user) => 
					(
						<tr key={user.id}>
							<td>{user.username}</td>
							<td>{user.email}</td>
							<td>
								<select value={user.role} onChange={(e) => handleRolechange(iduser, e.target.value)}>
									<option value="user">Utilisateur</option>
									<option value="admin">administrateur</option>
								</select>
							</td>
							<td>
								<button onClick={() => handledelete(user.id)}>Supprimer</button>
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

export default AdminUsers;