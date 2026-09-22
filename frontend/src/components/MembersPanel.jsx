import { useState } from "react";
import { addProjectMember, lookupUserByEmail, removeProjectMember } from "../services/projectService";
import { useTranslation } from "react-i18next";
import "./MembersPanel.css";

function MembersPanel({ projectId, members, currentUserId, onMembersChange })
{
	const [email, setEmail] = useState("");
	const [role, setRole] = useState("viewer");
	const [error, setError] = useState("");
	const [adding, setAdding] = useState(false);
	const { t } = useTranslation();

	const isOwner = members.some((m) => m.user_id === currentUserId && m.role === "owner");

	async function handleAdd(e)
	{
		e.preventDefault();
		if (!email.trim())
			return ;

		setAdding(true);
		setError("");
		try
		{
			const { user } = await lookupUserByEmail(email.trim());
			const { member } = await addProjectMember(projectId, user.id, role);
			onMembersChange([...members, member]);
			setEmail("");
		}
		catch (err)
		{
			setError(err.message);
		}
		finally
		{
			setAdding(false);
		}
	}

	async function handleRemove(userId)
	{
		try
		{
			await removeProjectMember(projectId, userId);
			onMembersChange(members.filter((m) => m.user_id !== userId));
		}
		catch (err)
		{
			setError(err.message);
		}
	}

	return (
		<div className="members-panel">
			<h3>{t("members.title")}</h3>
			<ul className="members-list">
				{members.map((member) => (
					<li key={member.id}>
						<span>{member.username}</span>
						<span className={`role-badge role-${member.role}`}>{t(`members.role.${member.role}`)}</span>
						{isOwner && member.user_id !== currentUserId && (
							<button onClick={() => handleRemove(member.user_id)}>{t("members.remove")}</button>
						)}
					</li>
				))}
			</ul>
			{isOwner && (
				<form onSubmit={handleAdd} className="members-add-form">
					<input
						type="email"
						placeholder={t("members.emailPlaceholder")}
						value={email}
						onChange={(e) => setEmail(e.target.value)}
					/>
					<select value={role} onChange={(e) => setRole(e.target.value)}>
						<option value="viewer">{t("members.role.viewer")}</option>
						<option value="editor">{t("members.role.editor")}</option>
						<option value="owner">{t("members.role.owner")}</option>
					</select>
					<button type="submit" disabled={adding}>
						{adding ? t("random.envoi") : t("members.add")}
					</button>
				</form>
			)}
			{error && <p className="error">{error}</p>}
		</div>
	);
}

export default MembersPanel;
