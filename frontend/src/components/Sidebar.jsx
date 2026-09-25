import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { isLoggedIn, logout } from "../services/authService";
import { getMe } from "../services/userservice";
import LanguageSwitcher from "./LanguageSwitcher";
import GamificationWidget from "./GamificationWidget";

const LINK_BASE = "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm font-semibold text-brand-sidebar-text transition-colors hover:bg-white/10 hover:text-white";
const LINK_ACTIVE = "bg-brand-primary text-white";

function navClass({ isActive })
{
	return `${LINK_BASE} ${isActive ? LINK_ACTIVE : ""}`;
}

function Sidebar()
{
	const loggedIn = isLoggedIn();
	const { t } = useTranslation();
	const [isAdmin, setIsAdmin] = useState(false);
	const navigate = useNavigate();

	function handleLogout()
	{
		logout();
		navigate("/login");
	}

	useEffect(() =>
	{
		if (!loggedIn)
		{
			setIsAdmin(false);
			return ;
		}
		getMe()
			.then((data) => setIsAdmin(data.user.role === "admin"))
			.catch(() => setIsAdmin(false));
	}, [loggedIn]);

	return (
		<aside className="flex w-60 shrink-0 flex-col gap-8 bg-gradient-to-b from-brand-sidebar to-brand-sidebar-alt px-4 py-6 font-sans text-brand-sidebar-text sm:sticky sm:top-0 sm:min-h-screen max-sm:w-full max-sm:flex-row max-sm:flex-wrap max-sm:items-center max-sm:gap-4">
			<div className="px-2 text-lg font-bold tracking-wide text-white">Task Manager</div>
			{loggedIn && (
				<nav className="flex flex-1 flex-col gap-1 max-sm:flex-row max-sm:flex-wrap">
					<NavLink to="/projects" className={navClass}>
						<span>📁</span> {t("navbar.projects")}
					</NavLink>
					<NavLink to="/search" className={navClass}>
						<span>🔍</span> {t("navbar.search")}
					</NavLink>
					<NavLink to="/profile" className={navClass}>
						<span>👤</span> {t("navbar.profile")}
					</NavLink>
					<NavLink to="/achievements" className={navClass}>
						<span>🏆</span> {t("navbar.achievements")}
					</NavLink>
					{isAdmin && (
						<NavLink to="/admin/users" className={navClass}>
							<span>🛡️</span> {t("navbar.users")}
						</NavLink>
					)}
				</nav>
			)}
			{loggedIn && <GamificationWidget />}
			<div className="flex flex-col gap-3 border-t border-white/10 pt-4 max-sm:flex-row max-sm:items-center max-sm:border-t-0 max-sm:pt-0">
				<LanguageSwitcher />
				{loggedIn ? (
					<button className={`${LINK_BASE} cursor-pointer border border-white/20 bg-transparent font-sans`} onClick={handleLogout}>
						<span>🚪</span> {t("navbar.logout")}
					</button>
				) : (
					<NavLink to="/login" className={LINK_BASE}>
						<span>🔑</span> {t("navbar.login")}
					</NavLink>
				)}
			</div>
		</aside>
	);
}

export default Sidebar;
