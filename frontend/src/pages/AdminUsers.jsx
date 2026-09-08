import { useState, useEffect } from "react";
import { getUser, userrole, deleteuser} from "../services/userservice.js";
import { useTranslation } from "react-i18next";

function AdminUsers ()
{
	const [Users, setUsers] = useState([]);
	const [ loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const { t } = useTranslation();

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
		if (!confirm(t("admin.rmuser")))
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
		return (<p>{t("loading.load")}</p>);
	if (error)
		return (<p className="error">{t("error.err")} : {error} </p>);
	return (
		<div className="admin-user-page">
			<h1>{t("admin.usermanag")}</h1>
			<table>
				<thread>
					<tr>
						<th>{t("login.username")}</th>
						<th>Email</th>
						<th>{t("admin.role")}</th>
						<th>{t("admin.action")}</th>
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
									<option value="user">{t("admin.user")}</option>
									<option value="admin">{t("admin.admin")}</option>
								</select>
							</td>
							<td>
								<button onClick={() => handledelete(user.id)}>{t("admin.delete")}</button>
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

export default AdminUsers;