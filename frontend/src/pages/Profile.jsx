import { useState, useEffect } from "react";
import { getMe, updateMe } from "../services/userservice";
import { isValidUsername } from "../utils/validation";
import { useTranslation } from "react-i18next";
import GdprPanel from "../components/GdprPanel";
import ProgressCard from "../components/ProgressCard";
import { getMyProgress } from "../services/gamificationService";
import './Profile.css';


function Profile() {
	const [user, setUser] = useState(null);
	const [error, setError] = useState("");
	const [loading, setLoading] = useState(true);
	const [editing, setEditing] = useState(false);
	const [username, setUsername] = useState("");
	const [saving, setSaving] = useState(false);
	const [saveError, setSaveError] = useState("");
	const [saved, setSaved] = useState(false);
	const [progress, setProgress] = useState(null);
	const { t } = useTranslation();

	useEffect(() => {
		async function fetchProfile() {
			try
			{
				const data = await getMe();
				setUser(data.user);
			}
			catch (err) {
				setError(err.message);
			}
			finally
			{
				setLoading(false);
			}
		}

	fetchProfile();
	getMyProgress()
		.then(setProgress)
		.catch(() => {});
	}, []);

	function startEdit()
	{
		setUsername(user.username);
		setSaved(false);
		setSaveError("");
		setEditing(true);
	}

	async function handleSave(e)
	{
		e.preventDefault();
		setSaveError("");
		if (!isValidUsername(username))
		{
			setSaveError(t("gdpr.usernameInvalid"));
			return ;
		}
		if (username === user.username)
		{
			setEditing(false);
			return ;
		}
		setSaving(true);
		try
		{
			const updated = await updateMe({ username });
			setUser(updated);
			setEditing(false);
			setSaved(true);
		}
		catch (err)
		{
			setSaveError(err.message);
		}
		finally
		{
			setSaving(false);
		}
	}

	if(loading)
		return <p>{t("loading.load")}</p>;
	if (error)
		return <p className="error">{t("error.err")} : {error}</p>;

	return (
		<div className="profile-page">
			<header className="profile-header">
				<h1>{t("profile.title")}</h1>
				<div className="profile-identity">
					<img className="profile-avatar" src={user.avatar_url} alt="" />
					<div>
						<p className="profile-username">{user.username}</p>
						<p className="profile-email">{user.email}</p>
					</div>
					{!editing && (
						<button type="button" className="profile-edit-button" onClick={startEdit}>
							{t("gdpr.editTitle")}
						</button>
					)}
				</div>
				{saved && <p className="profile-saved" role="status">{t("gdpr.saved")}</p>}
			</header>
			{editing && (
				<form className="profile-edit" onSubmit={handleSave} noValidate>
					<label htmlFor="profile-username">{t("login.username")}</label>
					<input
						id="profile-username"
						maxLength={50}
						value={username}
						onChange={(e) => setUsername(e.target.value)}
						required
						autoFocus
					/>
					<div className="profile-edit-actions">
						<button type="button" className="profile-edit-cancel" onClick={() => setEditing(false)} disabled={saving}>
							{t("gdpr.cancel")}
						</button>
						<button type="submit" disabled={saving}>
							{saving ? t("gdpr.saving") : t("gdpr.save")}
						</button>
					</div>
					{saveError && <p className="error" role="alert">{saveError}</p>}
				</form>
			)}
			{progress && <ProgressCard data={progress} />}
			<GdprPanel user={user} />
		</div>
	);
}

export default Profile;
