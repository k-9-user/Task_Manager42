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
	const [username, setUsername] = useState("");
	const [displayName, setDisplayName] = useState("");
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
				setUsername(data.user.username);
				setDisplayName(data.user.display_name ?? "");
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

	async function handleSave(e)
	{
		e.preventDefault();
		setSaved(false);
		setSaveError("");
		if (!isValidUsername(username))
		{
			setSaveError(t("gdpr.usernameInvalid"));
			return ;
		}
		setSaving(true);
		try
		{
			const updated = await updateMe({
				username,
				display_name: displayName.trim() || null,
			});
			setUser(updated);
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
				</div>
			</header>
			{progress && <ProgressCard data={progress} />}
			<form className="profile-edit" onSubmit={handleSave} noValidate>
				<h2>{t("gdpr.editTitle")}</h2>
				<label htmlFor="profile-username">{t("login.username")}</label>
				<input
					id="profile-username"
					maxLength={50}
					value={username}
					onChange={(e) => setUsername(e.target.value)}
					required
				/>
				<label htmlFor="profile-display-name">{t("gdpr.displayName")}</label>
				<input
					id="profile-display-name"
					maxLength={100}
					value={displayName}
					onChange={(e) => setDisplayName(e.target.value)}
				/>
				<button type="submit" disabled={saving}>
					{saving ? t("gdpr.saving") : t("gdpr.save")}
				</button>
				{saved && <p className="profile-saved" role="status">{t("gdpr.saved")}</p>}
				{saveError && <p className="error" role="alert">{saveError}</p>}
			</form>
			<GdprPanel user={user} />
		</div>
	);
}

export default Profile;
