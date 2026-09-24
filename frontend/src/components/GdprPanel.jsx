import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { logout } from "../services/authService";
import { deleteMyAccount, exportMyData } from "../services/gdprService";
import "./GdprPanel.css";

function GdprPanel({ user })
{
	const { t } = useTranslation();
	const navigate = useNavigate();
	const [exporting, setExporting] = useState(false);
	const [exportDone, setExportDone] = useState(false);
	const [confirming, setConfirming] = useState(false);
	const [typedUsername, setTypedUsername] = useState("");
	const [deleting, setDeleting] = useState(false);
	const [error, setError] = useState("");

	async function handleExport()
	{
		setExporting(true);
		setExportDone(false);
		setError("");
		try
		{
			await exportMyData();
			setExportDone(true);
		}
		catch (err)
		{
			setError(err.message);
		}
		finally
		{
			setExporting(false);
		}
	}

	function closeConfirm()
	{
		setConfirming(false);
		setTypedUsername("");
		setError("");
	}

	async function handleDelete(e)
	{
		e.preventDefault();
		if (typedUsername !== user.username)
			return ;
		setDeleting(true);
		setError("");
		try
		{
			await deleteMyAccount(typedUsername);
			logout();
			navigate("/login", { replace: true });
		}
		catch (err)
		{
			setError(err.message);
			setDeleting(false);
		}
	}

	return (
		<section className="gdpr-panel" aria-labelledby="gdpr-title">
			<h2 id="gdpr-title">{t("gdpr.title")}</h2>
			<p><Link to="/PrivacyPolicy#your-rights">{t("gdpr.rightsLink")}</Link></p>

			<div className="gdpr-block">
				<p>{t("gdpr.exportBody")}</p>
				<button type="button" onClick={handleExport} disabled={exporting}>
					{exporting ? t("gdpr.exporting") : t("gdpr.exportButton")}
				</button>
				{exportDone && <p className="gdpr-success" role="status">{t("gdpr.exportDone")}</p>}
			</div>

			<div className="gdpr-block">
				<p>
					{t("gdpr.deleteBody")}{" "}
					<Link to="/PrivacyPolicy#account-deletion">{t("gdpr.learnMore")}</Link>
				</p>
				{!confirming ? (
					<button type="button" className="gdpr-danger-button" onClick={() => setConfirming(true)}>
						{t("gdpr.deleteButton")}
					</button>
				) : (
					<form onSubmit={handleDelete}>
						<label htmlFor="gdpr-confirm-username">
							{t("gdpr.confirmLabel", { username: user.username })}
						</label>
						<input
							id="gdpr-confirm-username"
							value={typedUsername}
							onChange={(e) => setTypedUsername(e.target.value)}
							autoComplete="off"
							autoFocus
						/>
						<div className="gdpr-actions">
							<button type="button" onClick={closeConfirm} disabled={deleting}>
								{t("gdpr.cancel")}
							</button>
							<button
								type="submit"
								className="gdpr-danger-button"
								disabled={deleting || typedUsername !== user.username}
							>
								{deleting ? t("gdpr.deleting") : t("gdpr.confirmButton")}
							</button>
						</div>
					</form>
				)}
			</div>
			{error && <p className="error" role="alert">{t("error.err")} : {error}</p>}
		</section>
	);
}

export default GdprPanel;
