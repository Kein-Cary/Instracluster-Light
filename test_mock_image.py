"""
# this file use to creat a mock cluster with NFW model
and M/L = 50 M_sun/L_sun. 
accrding the light profile, we'll ctreat an image with 
real data(include redshift, pixel_size)
"""
import h5py
import numpy as np
from scipy import interpolate as interp
import astropy.units as U
import astropy.constants as C
import astropy.io.fits as fits
from astropy import cosmology as apcy

from resamp import gen
from ICL_surface_mass_density import sigma_m_c
from light_measure import light_measure, flux_recal, sigmam, sigmamc

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
# constant
c0 = U.kpc.to(U.cm)
c1 = U.Mpc.to(U.pc)
c2 = U.Mpc.to(U.cm)
c3 = U.L_sun.to(U.erg/U.s)
c4 = U.rad.to(U.arcsec)
c5 = U.pc.to(U.cm)
Lsun = C.L_sun.value*10**7
# cosmology model
Test_model = apcy.Planck15.clone(H0 = 67.74, Om0 = 0.311)
H0 = Test_model.H0.value
h = H0/100
Omega_m = Test_model.Om0
Omega_lambda = 1.-Omega_m
Omega_k = 1.- (Omega_lambda + Omega_m)

pixel = 0.396 # the pixel size in unit arcsec
z_ref = 0.250 
Da_ref = Test_model.angular_diameter_distance(z_ref).value
Jy = 10**(-23) # (erg/s)/cm^2
f0 = 3631*10**(-23) # zero point in unit (erg/s)/cm^-2

def SB_lightpro():
	"""
	sigma_m_c: calculate the 2D density profile of cluster, rho_2d
	R : r200, rbin: a radius array
	"""
	Mh = 15-np.log10(8) # make the radius close to 1 Mpc
	N = 131
	R, rho_2d, rbin = sigma_m_c(Mh, N)
	Lc = rho_2d/100 # in unit L_sun/kpc^2, Lc = Lc(r)
	
	# creat series cluster intrinsic SB profile
	with h5py.File('/home/xkchen/mywork/ICL/code/sample_catalog.h5') as f:
		catalogue = np.array(f['a'])
	z = catalogue[0]
	a = 1/(1+z)
	SB = 21.572 + 4.75 - 2.5*np.log10(10**(-6)*np.tile(Lc, (len(z),1))) + 10*np.log10(np.tile(z+1,(N,1)).T)

	Lz = np.tile(a**4,(N,1)).T*np.tile(Lc, (len(z),1))/(4*np.pi*c4**2) # L at z in unit: (Lsun/kpc^2)/arcsec^2
	Lob = Lz*Lsun/c0**2
	Iner_SB = 22.5-2.5*np.log10(Lob/(10**(-9)*f0))

	zt = z[0]
	Dat = Test_model.angular_diameter_distance(zt).value
	st = (10**(-6)/Dat**2)*c4**2
	ft = Lc*Lsun/(4*np.pi*(1+zt)**4*Dat**2)
	SBt = 22.5 - 2.5*np.log10(ft/(c2**2*f0*10**(-9)))+2.5*np.log10(st)

	with h5py.File('mock_flux_data.h5', 'w') as f:
		f['a'] = Lob

	with h5py.File('mock_mag_data.h5', 'w') as f:
		f['a'] = Iner_SB

	c_s = np.array([Lc, rbin])
	with h5py.File('mock_intric_SB.h5', 'w') as f:
		f['a'] = c_s
	with h5py.File('mock_intric_SB.h5') as f:
		for t in range(len(c_s)):
			f['a'][t,:] = c_s[t,:]

	return Lob, Iner_SB, z, rbin, R

def mock_image():

	Npi = 1000

	with h5py.File('mock_flux_data.h5') as f:
		Lob = np.array(f['a'])
	with h5py.File('mock_mag_data.h5') as f:
		Iner_SB = np.array(f['a'])
	with h5py.File('mock_intric_SB.h5') as f:
		Lc = np.array(f['a'][0])
		rbin = np.array(f['a'][1])
	R = np.max(rbin)
	r_sc = rbin/np.max(rbin)
	flux_func = interp.interp1d(r_sc, Lob[0], kind = 'cubic')

	x1 = np.linspace(-1.2*R, 1.2*R, 2*Npi+1)
	y1 = np.linspace(-1.2*R, 1.2*R, 2*Npi+1)
	plane = np.meshgrid(x1, y1)
	dr = np.sqrt((plane[0]-0)**2+(plane[1]-0)**2)
	dr_sc = dr/R
	test_dr = dr_sc[Npi+1, Npi+1:Npi+833]
	test = flux_func(test_dr)
	iat = r_sc <= test_dr[0]
	ibt = rbin[iat]
	ict = Lob[0][iat]

	mock_ana = np.zeros((2*Npi+1, 2*Npi+1), dtype = np.float)
	for k in range(len(test_dr)):
		if k == 0:
			mock_ana[Npi+1, Npi+1] = ict[-2]
		elif k == 1:
			mock_ana[Npi+1-1, Npi+1-1:Npi+1+2] = ict[-1]
			mock_ana[Npi+1+1, Npi+1-1:Npi+1+2] = ict[-1]
			mock_ana[Npi+1-1:Npi+1+2, Npi+1-1] = ict[-1]
			mock_ana[Npi+1-1:Npi+1+2, Npi+1+2] = ict[-1]
		else:
			ia = (dr_sc >= test_dr[k-1]) & (dr_sc < test_dr[k])
			ib = np.where(ia == True)
			mock_ana[ib[0], ib[1]] = flux_func(test_dr[k-1])

	plt.pcolormesh(plane[0], plane[1], mock_ana, cmap = 'plasma', norm = mpl.colors.LogNorm())
	plt.colorbar(label = '$flux[(erg/s)/cm^2]$')
	plt.xlabel('R[kpc]')
	plt.ylabel('R[kpc]')
	plt.savefig('mock_cluster_phy.png', dpi = 600)
	plt.show()
	plt.close()

	return

def mock_ccd():
	
	kz = 0
	with h5py.File('mock_flux_data.h5') as f:
		Lob = np.array(f['a'])
	with h5py.File('mock_mag_data.h5') as f:
		Iner_SB = np.array(f['a'])
	with h5py.File('mock_intric_SB.h5') as f:
		Lc = np.array(f['a'][0])
		rbin = np.array(f['a'][1])
	R = np.max(rbin)
	r_sc = rbin/np.max(rbin)
	flux_func = interp.interp1d(r_sc, Lob[kz], kind = 'cubic')

	with h5py.File('/home/xkchen/mywork/ICL/code/sample_catalog.h5') as f:
		catalogue = np.array(f['a'])
	z = catalogue[0]
	ra = catalogue[1]
	dec = catalogue[2]
	
	Da0 = Test_model.angular_diameter_distance(z[kz]).value
	Angu_r = (10**(-3)*R/Da0)*c4
	R_pixel = Angu_r/pixel
	r_in = (rbin*10**(-3)/Da0)*c4
	"""
	# scale as the size of observation
	(in case the cluster center is the frame center)
	"""
	y0 = np.linspace(0, 1488, 1489)
	x0 = np.linspace(0, 2047, 2048)
	frame = np.zeros((len(y0), len(x0)), dtype = np.float)
	pxl = np.meshgrid(x0, y0)

	def centered_loc(xc, yc):
		#xc = 1025
		#yc = 745
		xc = xc
		yc = yc
		dr = np.sqrt((pxl[0]-xc)**2+(pxl[1]-yc)**2)
		dr_sc = dr/R_pixel
		
		test_dr = dr_sc[yc, xc+1: xc+1+np.int(R_pixel)]
		test = flux_func(test_dr)
		iat = r_sc <= test_dr[0]
		ibt = r_in[iat]
		ict = Lob[kz][iat]

		for k in range(len(test_dr)):
			if k == 0:
				continue
			else:
				ia = (dr_sc >= test_dr[k-1]) & (dr_sc < test_dr[k])
				ib = np.where(ia == True)
				frame[ib[0], ib[1]] = flux_func(test_dr[k-1])*pixel**2/(f0*10**(-9))

		plt.imshow(frame, cmap = 'rainbow', origin = 'lower', norm = mpl.colors.LogNorm())
		plt.colorbar(label = 'flux[nMgy]', fraction = 0.035,pad = 0.003)
		plt.savefig('mock_frame.png', dpi =600)
		plt.show()
		
		x = frame.shape[1]
		y = frame.shape[0]
		keys = ['SIMPLE','BITPIX','NAXIS','NAXIS1','NAXIS2','CRPIX1','CRPIX2',
		        'CENTER_X','CENTER_Y','CRVAL1','CRVAL2','CENTER_RA','CENTER_DEC','ORIGN_Z',]
		value = ['T', 32, 2, x, y, np.int(xc), np.int(yc), xc, yc, xc, yc, ra[kz], dec[kz], z[kz]]
		ff = dict(zip(keys,value))
		fil = fits.Header(ff)

		fits.writeto('/home/xkchen/mywork/ICL/data/mock_frame/mock_frame_z%.3f_ra%.3f_dec%.3f.fits'
						%(z[kz], ra[kz], dec[kz]), frame, header = fil, overwrite=True)

		#fits.writeto('/home/xkchen/mywork/ICL/data/mock_frame/corner_frame_z%.3f_ra%.3f_dec%.3f.fits'
		#				%(z[kz], ra[kz], dec[kz]), frame, header = fil, overwrite=True)

		#fits.writeto('/home/xkchen/mywork/ICL/data/mock_frame/short_edge_frame_z%.3f_ra%.3f_dec%.3f.fits'
		#				%(z[kz], ra[kz], dec[kz]), frame, header = fil, overwrite=True)

		#fits.writeto('/home/xkchen/mywork/ICL/data/mock_frame/long_edge_frame_z%.3f_ra%.3f_dec%.3f.fits'
		#		%(z[kz], ra[kz], dec[kz]), frame, header = fil, overwrite=True)
		return

	# xc = 1025, yc = 745 # center location
	# xc = 2, yc = 2, # corner location
	# xc = 2, yc = 745, # short edge location
	# xc = 1025, yc = 2, # long edge location
	centered_loc(xc = 1025, yc = 745)
	return

def light_test():

	kz = 0
	with h5py.File('mock_flux_data.h5') as f:
		Lob = np.array(f['a'])
	with h5py.File('mock_mag_data.h5') as f:
		Iner_SB = np.array(f['a'])
	with h5py.File('mock_intric_SB.h5') as f:
		Lc = np.array(f['a'][0])
		rbin = np.array(f['a'][1])

	r_sc = rbin/np.max(rbin)
	flux_func = interp.interp1d(r_sc, Iner_SB[kz])

	with h5py.File('/home/xkchen/mywork/ICL/code/sample_catalog.h5') as f:
		catalogue = np.array(f['a'])
	z = catalogue[0]
	ra = catalogue[1]
	dec = catalogue[2]
	Da0 = Test_model.angular_diameter_distance(z[kz]).value

	mock_data = fits.getdata('/home/xkchen/mywork/ICL/data/mock_frame/mock_frame_z%.3f_ra%.3f_dec%.3f.fits'
				%(z[kz], ra[kz], dec[kz]), header = True)

	#mock_data = fits.getdata('/home/xkchen/mywork/ICL/data/mock_frame/corner_frame_z%.3f_ra%.3f_dec%.3f.fits'
	#			%(z[kz], ra[kz], dec[kz]), header = True)

	#mock_data = fits.getdata('/home/xkchen/mywork/ICL/data/mock_frame/short_edge_frame_z%.3f_ra%.3f_dec%.3f.fits'
	#			%(z[kz], ra[kz], dec[kz]), header = True)

	#mock_data = fits.getdata('/home/xkchen/mywork/ICL/data/mock_frame/long_edge_frame_z%.3f_ra%.3f_dec%.3f.fits'
	#			%(z[kz], ra[kz], dec[kz]), header = True)
	
	f = mock_data[0]
	r_in = ((rbin/10**3)/Da0)*c4
	Angur = (np.max(rbin/1000)/Da0)*c4
	Rp = Angur/pixel
	cx = mock_data[1]['CENTER_X']
	cy = mock_data[1]['CENTER_Y']

	test_data = f[cy, cx:]
	test_x = np.linspace(cx, f.shape[1]-1, f.shape[1]-cx)
	test_lit = 22.5-2.5*np.log10(test_data)+2.5*np.log10(pixel**2)
	test_com = test_lit[test_lit != np.inf]
	test_r = (test_x[test_lit != np.inf]- cx)*0.396
	test_R = test_r*Da0*10**3/c4
	
	ia = Iner_SB[kz][(Iner_SB[kz] >= np.min(test_com)) & (Iner_SB[kz] <= np.max(test_com))]
	nr = np.linspace(np.min(test_R), np.max(test_R), len(test_com))
	compare_l = flux_func(nr/np.max(rbin))
	plt.figure(figsize = (16,9))
	'''
	plt.plot(test_R, test_com, 'r--', label = 'SB_ccd', alpha = 0.5)
	plt.plot(rbin, Iner_SB[kz], 'b-', label = 'SB_theory', alpha = 0.5)
	plt.legend(loc = 3)
	plt.xlabel('R[arcsec]')
	plt.ylabel('$SB[mag/arcsec^2]$')
	plt.xscale('log')
	plt.gca().invert_yaxis()
	plt.savefig('mock2ccd_test.png', dpi = 600)
	plt.close()
	'''
	
	gs1 = gridspec.GridSpec(2,1, height_ratios = [4,1])
	ax1 = plt.subplot(gs1[0])
	ax2 = plt.subplot(gs1[1])

	ax1.plot(test_R, test_com, 'r--', label = 'SB_ccd', alpha = 0.5)
	ax1.plot(nr, compare_l, 'b-', label = 'SB_theory', alpha = 0.5)
	ax1.legend(loc = 3)
	ax1.set_xlabel('R[arcsec]')
	ax1.set_ylabel('$SB[mag/arcsec^2]$')
	ax1.set_xscale('log')
	ax1.invert_yaxis()

	ax2.plot(test_R, compare_l - test_com, label = '$\Delta_{SB}$')
	ax2.legend(loc = 1)
	ax2.set_xlabel('R[arcsec]')
	ax2.set_ylabel('$SB[mag/arcsec^2]$')
	ax2.set_xscale('log')

	plt.savefig('mock2ccd_test.png', dpi = 600)
	plt.show()
	raise
	light, R, Ar1 = light_measure(f, 50, 2, Rp, cx, cy, pixel, z[kz])
	plt.figure(figsize = (16,9))
	plt.plot(Ar1, light, 'r*--', label = 'SB_ccd', alpha = 0.5)
	plt.plot(r_in, Iner_SB[kz], 'b-', label = 'SB_theory', alpha = 0.5)
	plt.legend(loc = 1)
	plt.xscale('log')
	plt.gca().invert_yaxis()
	plt.xlabel('R[arcsec]')
	plt.ylabel('$SB[mag/arcsec^2]$')
	plt.savefig('ccd_light_measure.png', dpi = 600)
	plt.close()

	L_ref = Da_ref*pixel/c4 
	L_z0 = Da0*pixel/c4
	b = L_ref/L_z0
	xn,yn,resam = gen(f, 1, b, cx, cy)
	test_resam, R_resam, r0_resam = light_measure(resam, 50, 2, Rp/b, xn, yn, pixel*b, z[kz])
	
	plt.imshow(resam, cmap = 'rainbow', origin = 'lower', norm = mpl.colors.LogNorm())
	plt.colorbar(label = 'flux[nMgy]', fraction = 0.035, pad = 0.003)
	plt.savefig('resam_compare.png', dpi = 600)
	plt.close()
	
	plt.figure(figsize = (16,9))
	plt.plot(r0_resam, test_resam, 'r*--', label = 'SB_resample', alpha = 0.5)
	plt.plot(r_in, Iner_SB[kz], 'b-', label = 'SB_theory', alpha = 0.5)
	plt.xlabel('R[arcsec]')
	plt.xscale('log')
	plt.ylabel('$SB[mag/arcsec^2]$')
	plt.legend(loc = 3)
	plt.gca().invert_yaxis()
	plt.savefig('mock_resam_test.png', dpi = 600)
	plt.close()
	
	return

def resample_test():

	kz = 0
	with h5py.File('mock_flux_data.h5') as f:
		Lob = np.array(f['a'])
	with h5py.File('mock_mag_data.h5') as f:
		Iner_SB = np.array(f['a'])
	with h5py.File('mock_intric_SB.h5') as f:
		Lc = np.array(f['a'][0])
		rbin = np.array(f['a'][1])
	SB0 = Iner_SB[0]
	R0 = np.max(rbin)*10**(-3)

	with h5py.File('/home/xkchen/mywork/ICL/code/sample_catalog.h5') as f:
		catalogue = np.array(f['a'])
	z = catalogue[0]
	ra = catalogue[1]
	dec = catalogue[2]

	#f_data = fits.getdata('/home/xkchen/mywork/ICL/data/mock_frame/mock_frame_z%.3f_ra%.3f_dec%.3f.fits'
	#			%(z[kz], ra[kz], dec[kz]), header = True)

	#f_data = fits.getdata('/home/xkchen/mywork/ICL/data/mock_frame/corner_frame_z%.3f_ra%.3f_dec%.3f.fits'
	#			%(z[kz], ra[kz], dec[kz]), header = True)

	#f_data = fits.getdata('/home/xkchen/mywork/ICL/data/mock_frame/short_edge_frame_z%.3f_ra%.3f_dec%.3f.fits'
	#			%(z[kz], ra[kz], dec[kz]), header = True)

	f_data = fits.getdata('/home/xkchen/mywork/ICL/data/mock_frame/long_edge_frame_z%.3f_ra%.3f_dec%.3f.fits'
				%(z[kz], ra[kz], dec[kz]), header = True)

	Da0 = Test_model.angular_diameter_distance(z[kz]).value

	Angur = (R0/Da0)*c4
	Rp = Angur/pixel
	cx = f_data[1]['CENTER_X']
	cy = f_data[1]['CENTER_Y']
	L_ref = Da_ref*pixel/c4 
	L_z0 = Da0*pixel/c4
	b = L_ref/L_z0
	Rref = (R0*c4/Da_ref)/pixel

	r0 = (rbin/1000)*c4/Da0
	r0_0 = (rbin/1000)*c4/Da_ref
	SB_0 = SB0 + 10*np.log10((1+z_ref)/(1+z[kz]))

	f = f_data[0]
	f_goal = flux_recal(f, z[kz], z_ref)
	SB_1, R_1, r0_1 = light_measure(f_goal, 50, 2, Rp, cx, cy, pixel/b, z[kz])
	xn, yn, resam = gen(f_goal, 1, b, cx, cy)
	SB_2, R_2, r0_2 = light_measure(resam, 50, 2, Rref, xn, yn, pixel, z[kz])
	
	plt.figure(figsize = (16, 9))
	plt.plot(r0_0, SB_0, 'r--', label = 'SB_zref', alpha = 0.5)
	#plt.plot(r0_1, SB_1, 'b-', label = 'SB_scale', alpha = 0.5)
	plt.plot(r0_2, SB_2, 'g--', label = 'SB_resample', alpha = 0.5)
	plt.plot(r0, SB0, 'k-', label = 'SB_z0')
	plt.xlabel('R[arcsec]')

	plt.ylabel('$ SB[mag/arcsec^2] $')
	plt.xscale('log')
	plt.legend(loc = 3)
	plt.gca().invert_yaxis()
	plt.grid(alpha = 0.5)
	plt.savefig('c_cen_resam_line.png')
	plt.close()
	
	return

def test():
	#SB_lightpro()
	#mock_image()
	mock_ccd()
	#light_test()
	#resample_test()

def main():
	test()

if __name__ == '__main__' :
	main()