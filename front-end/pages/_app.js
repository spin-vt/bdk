import '../styles/globals.css'
import EditMapProvider from '../contexts/EditMapProvider'
import { FolderProvider } from "../contexts/FolderContext";
import FetchTaskInfoProvider from '../contexts/FetchTaskInfoProvider';
import ReloadMapProvider from "../contexts/ReloadMapProvider";

function MyApp({ Component, pageProps }) {
  return (
    <FolderProvider>
      <EditMapProvider>
        <FetchTaskInfoProvider>
          <ReloadMapProvider>
          <Component {...pageProps} />
          </ReloadMapProvider>
        </FetchTaskInfoProvider>
      </EditMapProvider>
    </FolderProvider>

  )
}

export default MyApp
