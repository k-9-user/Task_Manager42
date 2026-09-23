import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import './PrivacyPolicy.css';

const GDPR_RIGHTS = ["access", "rectification", "erasure", "restriction", "automated"];

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
			<p>{t("legal.privacy.section4Intro")}</p>
			<ul className="legal-rights">
				{GDPR_RIGHTS.map((right) => (
					<li key={right}>
						<strong>{t(`legal.privacy.rights.${right}.name`)}</strong>{" "}
						{t(`legal.privacy.rights.${right}.body`)}
					</li>
				))}
			</ul>
			<p>{t("legal.privacy.section4Footer")}</p>
			<p><Link to="/Profile">{t("legal.privacy.profileLink")}</Link></p>
			<h2>{t("legal.privacy.section5Title")}</h2>
			<p>{t("legal.privacy.section5Body")}</p>
			<h2>{t("legal.privacy.contactTitle")}</h2>
			<p>{t("legal.privacy.contactBody")}</p>
		</div>
	);
}

export default PrivacyPolicy;
