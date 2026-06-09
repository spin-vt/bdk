import '../styles/globals.css'
import EditMapProvider from '../contexts/EditMapProvider'
import { FolderProvider } from "../contexts/FolderContext";
import FetchTaskInfoProvider from '../contexts/FetchTaskInfoProvider';
import ReloadMapProvider from "../contexts/ReloadMapProvider";
import ImpersonationBanner from "../components/ImpersonationBanner";

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
