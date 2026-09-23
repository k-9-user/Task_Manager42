import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { deleteMyAccount, exportMyData } from "../services/gdprService";
import "./GdprPanel.css";

const RIGHTS = ["access", "rectification", "erasure", "restriction", "automated"];
const DELETE_EFFECTS = ["projects", "content", "tasks", "files", "admin"];

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
			localStorage.removeItem("token");
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
			<p>{t("gdpr.intro")}</p>

			<h3>{t("gdpr.rightsTitle")}</h3>
			<ul className="gdpr-rights">
				{RIGHTS.map((right) => (
					<li key={right}>
						<strong>{t(`gdpr.rights.${right}.name`)}</strong>{" "}
						{t(`gdpr.rights.${right}.body`)}
					</li>
				))}
			</ul>
			<p className="gdpr-note">{t("gdpr.emailNote")}</p>

			<div className="gdpr-block">
				<h3>{t("gdpr.exportTitle")}</h3>
				<p>{t("gdpr.exportBody")}</p>
				<button type="button" onClick={handleExport} disabled={exporting}>
					{exporting ? t("gdpr.exporting") : t("gdpr.exportButton")}
				</button>
				{exportDone && <p className="gdpr-success" role="status">{t("gdpr.exportDone")}</p>}
			</div>

			<div className="gdpr-block gdpr-danger">
				<h3>{t("gdpr.deleteTitle")}</h3>
				<p>{t("gdpr.deleteIntro")}</p>
				<ul>
					{DELETE_EFFECTS.map((effect) => (
						<li key={effect}>{t(`gdpr.deleteEffects.${effect}`)}</li>
					))}
				</ul>
				<p><strong>{t("gdpr.irreversible")}</strong></p>
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
