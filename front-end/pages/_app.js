import '../styles/globals.css'
import EditMapProvider from '../contexts/EditMapProvider'
import { FolderProvider } from "../contexts/FolderContext";
import FetchTaskInfoProvider from '../contexts/FetchTaskInfoProvider';
import ReloadMapProvider from "../contexts/ReloadMapProvider";
import ImpersonationBanner from "../components/ImpersonationBanner";
import { installCsrfFetch } from "../utils/csrf";

// Every mutating API call must carry the CSRF header; wrap fetch once,
// globally, before any component code runs (no-op during SSR).
installCsrfFetch();

function MyApp({ Component, pageProps }) {
  return (
    <FolderProvider>
      <EditMapProvider>
        <FetchTaskInfoProvider>
          <ReloadMapProvider>
          <ImpersonationBanner />
          <Component {...pageProps} />
          </ReloadMapProvider>
        </FetchTaskInfoProvider>
      </EditMapProvider>
    </FolderProvider>

  )
}

export default MyApp
