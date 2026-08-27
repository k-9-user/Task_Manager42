import { Link } from "react-router-dom";

function Footer() {
	return (
		<footer className="footer">
			<p>&copy; 2026 Task Manager</p>
			<div className="footer-links">
				<Link to="/PrivacyPolicy">Politique de confidentialité</Link>
				<p>				</p>
				<Link to="/TermsOfService">Conditions d'utilisation</Link>
			</div>
		</footer>
	);
}

export default Footer;