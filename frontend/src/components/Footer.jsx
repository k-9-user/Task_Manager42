import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import './Footer.css'

function Footer() {
	const { t } = useTranslation();
	return (
		<footer className="footer">
			<p>&copy; 2026 Task Manager</p>
			<div className="footer-links">
				<Link className="condition-link" to="/PrivacyPolicy">{t("footer.pc")}</Link>
				<Link className="condition-link" to="/TermsOfService">{t("footer.cdu")}</Link>
			</div>
		</footer>
	);
}

export default Footer;