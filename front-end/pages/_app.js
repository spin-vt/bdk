import '../styles/globals.css'
import EditMapProvider from '../contexts/EditMapProvider'
import { FolderProvider } from "../contexts/FolderContext";
import FetchTaskInfoProvider from '../contexts/FetchTaskInfoProvider';

function MyApp({ Component, pageProps }) {
  return (
    <FolderProvider>
      <EditMapProvider>
        <FetchTaskInfoProvider>
          <Component {...pageProps} />
        </FetchTaskInfoProvider>
      </EditMapProvider>
    </FolderProvider>

  )
}

export default MyApp
