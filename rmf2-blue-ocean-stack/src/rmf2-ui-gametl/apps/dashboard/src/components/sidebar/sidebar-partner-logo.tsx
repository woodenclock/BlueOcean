import { Box, Image } from '@chakra-ui/react';
import rosApLogo from '@/assets/ros-ap-logo.png';

export interface SidebarPartnerLogoProps {
  collapsed?: boolean;
}

export function SidebarPartnerLogo({
  collapsed = false,
}: SidebarPartnerLogoProps) {
  if (collapsed) {
    return null;
  }

  return (
    <Box
      w="100%"
      display="flex"
      flexDirection="column"
      alignItems="center"
      px="20px"
    >
      <Box h="1px" w="100%" bg="rgba(135, 140, 189, 0.3)" mb="16px" />
      <Box
        bg="white"
        p="12px"
        borderRadius="8px"
        w="100%"
        maxW="220px"
        display="flex"
        justifyContent="center"
      >
        <Image
          src={rosApLogo}
          alt="ROS Industrial Consortium Asia Pacific"
          maxW="200px"
          w="100%"
          objectFit="contain"
        />
      </Box>
    </Box>
  );
}

export default SidebarPartnerLogo;
