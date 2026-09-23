import { useTranslation } from "react-i18next";
import { BADGE_ICONS } from "../utils/gamification";
import "./UserBadge.css";

function UserBadge({ level, badge })
{
	const { t } = useTranslation();
	const levelText = t("gamification.levelLong", { level });

	return (
		<span className={`user-badge ${badge ? "user-badge-earned" : ""}`.trim()} title={levelText}>
			{badge && <span aria-hidden="true">{BADGE_ICONS[badge]}</span>}
			{badge && <span>{t(`gamification.badges.${badge}`)}</span>}
			<span className="user-badge-level" aria-hidden="true">{t("gamification.levelShort", { level })}</span>
			<span className="sr-only">{levelText}</span>
		</span>
	);
}

export default UserBadge;
