import '../styles/globals.css'
import EditMapProvider from '../contexts/EditMapProvider'
import { FolderProvider } from "../contexts/FolderContext";


function MyApp({ Component, pageProps }) {
  return (
    <FolderProvider>

    <EditMapProvider>
      <Component {...pageProps} />
    </EditMapProvider>
    </FolderProvider>

  )
}

export default MyApp
