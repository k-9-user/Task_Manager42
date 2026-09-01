import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

function Footer() {
	const { t } = useTranslation();
	return (
		<footer className="footer">
			<p>&copy; 2026 Task Manager</p>
			<div className="footer-links">
				<Link to="/PrivacyPolicy">{t("footer.pc")}</Link>
				<p>				</p>
				<Link to="/TermsOfService">{t("footer.cdu")}</Link>
			</div>
		</footer>
	);
}

export default Footer;