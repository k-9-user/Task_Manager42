import { useState, useEffect } from "react";
import { getUser, userrole, userstatus, deleteuser} from "../services/userservice.js";
import { useTranslation } from "react-i18next";
import './AdminUsers.css';

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
				setUsers(data.users);
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
		const previous = Users;
		setUsers(Users.map((u) => (u.id === iduser ? { ...u, role: newrole } : u)));

		try
		{
			await userrole(iduser, newrole);
		}
		catch (err)
		{
			setUsers(previous);
			setError(err.message);
		}
	}

	async function handleStatusChange(iduser, newstatus)
	{
		const previous = Users;
		setUsers(Users.map((u) => (u.id === iduser ? { ...u, status: newstatus } : u)));

		try
		{
			await userstatus(iduser, newstatus);
		}
		catch (err)
		{
			setUsers(previous);
			setError(err.message);
		}
	}

	async function handledelete(iduser)
	{
		if (!confirm(t("admin.rmuser")))
			return ;
		const previous = Users;
		setUsers(Users.filter((u) => u.id !== iduser));

		try
		{
			await deleteuser(iduser);
		}
		catch (err)
		{
			setUsers(previous);
			setError(err.message);
		}
	}

	if (loading)
		return (<p>{t("loading.load")}</p>);
	return (
		<div className="admin-user-page">
			<h1>{t("admin.usermanag")}</h1>
			{error && <p className="error">{t("error.err")} : {error}</p>}
			<table>
				<thead>
					<tr>
						<th>{t("login.username")}</th>
						<th>Email</th>
						<th>{t("admin.role")}</th>
						<th>{t("admin.status")}</th>
						<th>{t("admin.action")}</th>
					</tr>
				</thead>
				<tbody>
					{Users.map((user) =>
					(
						<tr key={user.id}>
							<td>{user.username}</td>
							<td>{user.email}</td>
							<td>
								<select value={user.role} onChange={(e) => handleRolechange(user.id, e.target.value)}>
									<option value="user">{t("admin.user")}</option>
									<option value="admin">{t("admin.admin")}</option>
								</select>
							</td>
							<td>
								<span className={`status-badge status-${user.status}`}>
									{user.status === "banned" ? t("admin.banned") : t("admin.active")}
								</span>
							</td>
							<td className="admin-actions">
								{user.status === "banned" ? (
									<button onClick={() => handleStatusChange(user.id, "active")}>{t("admin.restore")}</button>
								) : (
									<button onClick={() => handleStatusChange(user.id, "banned")}>{t("admin.ban")}</button>
								)}
								<button className="danger" onClick={() => handledelete(user.id)}>{t("admin.delete")}</button>
							</td>
						</tr>
					))}
					{Users.length === 0 && (
						<tr>
							<td colSpan={5}>{t("admin.empty")}</td>
						</tr>
					)}
				</tbody>
			</table>
		</div>
	);
}

export default AdminUsers;
