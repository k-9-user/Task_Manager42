import { useTranslation } from "react-i18next";
import './LanguageSwitcher.css';


function LanguageSwitcher()
{
	const { t, i18n } = useTranslation();

	function handleChange(e)
	{
		i18n.changeLanguage(e.target.value);
	}

	return (
		<select className="language-switcher" aria-label={t("navbar.language")} value={i18n.language} onChange={handleChange}>
			<option value="fr">🇫🇷 Français</option>
			<option value="en">🇬🇧 English</option>
			<option value="es">🇪🇸 Español</option>
		</select>
	);
}

export default LanguageSwitcher;