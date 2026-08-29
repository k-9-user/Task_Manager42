import { Link } from "react-router-dom";
import './Navbar.css';
import { useAuth } from "../hooks/useAuth";
import { useTranslation } from "react-i18next";
import LanguageSwitcher from "./LanguageSwitcher";

function Navbar()
{
	const { isAuthen, logout } = useAuth();
	const {t} = useTranslation();

	return (
		<nav className="navbar">
			<div className="navbar-logo">Task Manager</div>
			<div className="navbar-links">
				<Link to="/projects">{t("navbar.projects")} </Link>
				{ isAuthen ?
					(
						<button onClick={logout}>{t("navbar.logout")}</button>
					)
					:
					(
						<Link to="/login">{t("navbar.login")}</Link>
					)
				}
				<Link to="/Search">{t("navbar.search")}</Link>
				<LanguageSwitcher />
			</div>
		</nav>
	);
}

export default Navbar;