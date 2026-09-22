import { useTranslation } from 'react-i18next';
import './PrivacyPolicy.css';

function PrivacyPolicy ()
{
	const { t } = useTranslation();

	return (
		<div className="legal-page">
			<h1>{t("legal.privacy.title")}</h1>
			<p><em>{t("legal.updated")}</em></p>
			<h2>{t("legal.privacy.section1Title")}</h2>
			<p>{t("legal.privacy.section1Body")}</p>
			<h2>{t("legal.privacy.section2Title")}</h2>
			<p>{t("legal.privacy.section2Body")}</p>
			<h2>{t("legal.privacy.section3Title")}</h2>
			<p>{t("legal.privacy.section3Body")}</p>
			<h2>{t("legal.privacy.section4Title")}</h2>
			<p>{t("legal.privacy.section4Body")}</p>
			<h2>{t("legal.privacy.section5Title")}</h2>
			<p>{t("legal.privacy.section5Body")}</p>
			<h2>{t("legal.privacy.contactTitle")}</h2>
			<p>{t("legal.privacy.contactBody")}</p>
		</div>
	);
}

export default PrivacyPolicy;
