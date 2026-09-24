import { useState, useEffect } from "react";
import { getUsers, getMe, setUserRole, setUserStatus, deleteUser, updateUser } from "../services/userservice.js";
import { isValidUsername } from "../utils/validation";
import { useTranslation } from "react-i18next";
import './AdminUsers.css';

const PAGE_SIZE = 20;

const ERROR_KEYS = {
	"At least one administrator is required": "admin.errors.lastAdmin",
	"At least one active administrator is required": "admin.errors.lastAdmin",
	"The bootstrap administrator is protected": "admin.errors.bootstrap",
	"Username already taken": "admin.errors.usernameTaken",
	"User not found": "admin.errors.notFound",
};

function AdminUsers ()
{
	const [users, setUsers] = useState([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [search, setSearch] = useState("");
	const [query, setQuery] = useState("");
	const [role, setRole] = useState("");
	const [status, setStatus] = useState("");
	const [reloadKey, setReloadKey] = useState(0);
	const [meId, setMeId] = useState(null);
	const [editing, setEditing] = useState(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const { t } = useTranslation();

	useEffect(() =>
	{
		getMe()
			.then((data) => setMeId(data.user.id))
			.catch(() => {});
	}, []);

	useEffect(() =>
	{
		let cancelled = false;
		setLoading(true);
		getUsers({ page, limit: PAGE_SIZE, q: query, role, status })
			.then((data) =>
			{
				if (cancelled)
					return ;
				if (data.users.length === 0 && page > 1)
				{
					setPage(page - 1);
					return ;
				}
				setUsers(data.users);
				setTotal(data.total);
			})
			.catch((err) => { if (!cancelled) setError(err.message); })
			.finally(() => { if (!cancelled) setLoading(false); });
		return () => { cancelled = true; };
	}, [page, query, role, status, reloadKey]);

	function describe(message)
	{
		return (ERROR_KEYS[message] ? t(ERROR_KEYS[message]) : message);
	}

	function handleSearch(e)
	{
		e.preventDefault();
		setQuery(search.trim());
		setPage(1);
	}

	async function handleRoleChange(userId, newRole)
	{
		const previous = users;
		setError("");
		setUsers(users.map((u) => (u.id === userId ? { ...u, role: newRole } : u)));

		try
		{
			await setUserRole(userId, newRole);
		}
		catch (err)
		{
			setUsers(previous);
			setError(err.message);
		}
	}

	async function handleStatusChange(user, newStatus)
	{
		if (newStatus === "banned" && !confirm(t("admin.confirmBan", { username: user.username })))
			return ;
		const previous = users;
		setError("");
		setUsers(users.map((u) => (u.id === user.id ? { ...u, status: newStatus } : u)));

		try
		{
			await setUserStatus(user.id, newStatus);
		}
		catch (err)
		{
			setUsers(previous);
			setError(err.message);
		}
	}

	async function handleDelete(user)
	{
		if (!confirm(t("admin.rmuser", { username: user.username })))
			return ;
		const previous = users;
		setError("");
		setUsers(users.filter((u) => u.id !== user.id));

		try
		{
			await deleteUser(user.id);
			setReloadKey((key) => key + 1);
		}
		catch (err)
		{
			setUsers(previous);
			setError(err.message);
		}
	}

	function startEdit(user)
	{
		setError("");
		setEditing({ id: user.id, username: user.username, display_name: user.display_name ?? "" });
	}

	async function handleSave(user)
	{
		const username = editing.username.trim();
		const displayName = editing.display_name.trim() || null;
		if (!isValidUsername(username))
		{
			setError(t("gdpr.usernameInvalid"));
			return ;
		}
		const fields = {};
		if (username !== user.username)
			fields.username = username;
		if (displayName !== user.display_name)
			fields.display_name = displayName;
		if (Object.keys(fields).length === 0)
		{
			setEditing(null);
			return ;
		}
		setError("");

		try
		{
			const data = await updateUser(user.id, fields);
			setUsers(users.map((u) => (u.id === user.id ? data.user : u)));
			setEditing(null);
		}
		catch (err)
		{
			setError(err.message);
		}
	}

	const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

	return (
		<div className="admin-user-page">
			<h1>{t("admin.usermanag")}</h1>
			<div className="admin-toolbar">
				<form className="admin-search" onSubmit={handleSearch}>
					<input
						type="search"
						value={search}
						maxLength={255}
						placeholder={t("admin.search")}
						aria-label={t("admin.search")}
						onChange={(e) => setSearch(e.target.value)}
					/>
					<button type="submit">{t("admin.searchButton")}</button>
				</form>
				<select value={role} aria-label={t("admin.role")} onChange={(e) => { setRole(e.target.value); setPage(1); }}>
					<option value="">{t("admin.allRoles")}</option>
					<option value="user">{t("admin.user")}</option>
					<option value="admin">{t("admin.admin")}</option>
				</select>
				<select value={status} aria-label={t("admin.status")} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
					<option value="">{t("admin.allStatuses")}</option>
					<option value="active">{t("admin.active")}</option>
					<option value="banned">{t("admin.banned")}</option>
				</select>
			</div>
			{error && <p className="error" role="alert">{t("error.err")} : {describe(error)}</p>}
			{loading && <p role="status">{t("loading.load")}</p>}
			<table>
				<thead>
					<tr>
						<th>{t("login.username")}</th>
						<th>{t("admin.email")}</th>
						<th>{t("admin.role")}</th>
						<th>{t("admin.status")}</th>
						<th>{t("admin.action")}</th>
					</tr>
				</thead>
				<tbody>
					{users.map((user) =>
					{
						const isSelf = user.id === meId;
						const isEditing = editing?.id === user.id;
						const selfTitle = isSelf ? t("admin.selfLocked") : undefined;
						return (
							<tr key={user.id}>
								<td>
									{isEditing ? (
										<div className="admin-edit">
											<input
												value={editing.username}
												maxLength={50}
												aria-label={t("login.username")}
												onChange={(e) => setEditing({ ...editing, username: e.target.value })}
											/>
											<input
												value={editing.display_name}
												maxLength={100}
												placeholder={t("admin.displayName")}
												aria-label={t("admin.displayName")}
												onChange={(e) => setEditing({ ...editing, display_name: e.target.value })}
											/>
										</div>
									) : (
										<>
											<span>{user.username}</span>
											{isSelf && <span className="self-badge">{t("admin.you")}</span>}
											{user.display_name && <span className="admin-display-name">{user.display_name}</span>}
										</>
									)}
								</td>
								<td>{user.email}</td>
								<td>
									<select
										value={user.role}
										disabled={isSelf}
										title={selfTitle}
										aria-label={t("admin.role")}
										onChange={(e) => handleRoleChange(user.id, e.target.value)}
									>
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
									{isEditing ? (
										<>
											<button onClick={() => handleSave(user)}>{t("admin.save")}</button>
											<button onClick={() => setEditing(null)}>{t("admin.cancel")}</button>
										</>
									) : (
										<>
											<button onClick={() => startEdit(user)}>{t("admin.edit")}</button>
											{user.status === "banned" ? (
												<button onClick={() => handleStatusChange(user, "active")}>{t("admin.restore")}</button>
											) : (
												<button disabled={isSelf} title={selfTitle} onClick={() => handleStatusChange(user, "banned")}>{t("admin.ban")}</button>
											)}
											<button className="danger" disabled={isSelf} title={selfTitle} onClick={() => handleDelete(user)}>{t("admin.delete")}</button>
										</>
									)}
								</td>
							</tr>
						);
					})}
					{!loading && users.length === 0 && (
						<tr>
							<td colSpan={5}>{t("admin.empty")}</td>
						</tr>
					)}
				</tbody>
			</table>
			<div className="admin-pagination">
				<button onClick={() => setPage(page - 1)} disabled={loading || page <= 1}>{t("admin.prev")}</button>
				<span>{t("admin.page", { page, pages })}</span>
				<button onClick={() => setPage(page + 1)} disabled={loading || page >= pages}>{t("admin.next")}</button>
			</div>
		</div>
	);
}

export default AdminUsers;
